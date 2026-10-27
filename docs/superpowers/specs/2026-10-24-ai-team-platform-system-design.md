# AI 团队平台系统设计（总体 + 分阶段）

> 日期：2026-10-24（2026-10-27 评审通过定稿）
> 状态：已定稿
> 前置文档：[2026-10-23-ai-team-platform-feasibility.md](./2026-10-23-ai-team-platform-feasibility.md)（决策与 WHY）
> 本文档回答 HOW：模块划分、接口契约、API/协议、数据迁移、各阶段交付的系统设计。

---

## 1. 总体系统设计

### 1.1 系统上下文

```
                    ┌──────────────┐
   人类用户 ────────>│  Web 前端     │  团队工作台 / HITL 审批 / 用量看板
   (org owner/admin  │  (Next.js)   │
    /member)         └──────┬───────┘
                          │ REST + SSE
                          ▼
┌────────────────────────────────────────────────────────────┐
│ FastAPI 单体 (apps/api)                                     │
│                                                            │
│  Routers ──> TeamRuntime（新）──> SkillRunner（现有）        │
│                │  信箱/预算/权限/计量          │             │
│                ▼                              ▼            │
│         Mailbox / MemoryStore          Skill / Tool 层(现有) │
│         ContextGovernor / RiskEngine   （数据访问唯一入口）    │
│  APScheduler（Phase 2）                                     │
└──────┬──────────────┬───────────────┬──────────────────────┘
       ▼              ▼               ▼
   Postgres       LLM Provider    Langfuse(自托管) / Sentry
  (pgvector,      (OpenAI 兼容)    （可观测，降级安全）
   全部业务表)
```

边界约束（继承可行性方案）：

- Agent 无原生算力，一切能力经 Skill/Tool 层（数据访问唯一入口，权限收口点）。
- 可观测组件降级安全：Langfuse/Sentry 故障不影响主流程。
- 单体优先：MVP 不拆服务，TeamRuntime 是进程内模块；队列化是 Phase 2 的部署形态变化，不是架构重写。

### 1.2 模块划分与代码结构

新增代码集中在 `apps/api/app/team/`（与现有 `agents/ skills/ tools/ services/` 平级），模型与路由按现有惯例放 `models/` `routers/`：

```
apps/api/app/
├── team/                          # ★ 新增：团队运行时内核
│   ├── runtime.py                 # TeamRuntime：execute/interrupt/resume/cancel 入口
│   ├── supervisor.py              # Supervisor 循环（规划/dispatch/验收/升级）
│   ├── worker.py                  # Worker 执行（包装 SkillRunner.run_with_react）
│   ├── sup_tools.py               # supervisor 专属 LLM 工具：dispatch/consult/
│   │                              #   request_human/finalize/reassign
│   ├── mailbox.py                 # Mailbox：task_messages 读写 + wait_for
│   ├── budget.py                  # 四级预算：预检/切分/预警/硬停
│   ├── permission.py              # PermissionEngine：effective_grants + check_tool
│   ├── governor.py                # ContextGovernor：弹性上下文装配（统一两套 ContextPack）
│   ├── memory.py                  # MemoryStore：三层记忆 + 蒸馏（Phase 2）
│   ├── risk.py                    # RiskEngine：限速/异常熔断/kill switch（Phase 2）
│   └── scheduler_svc.py           # schedules + APScheduler 封装（Phase 2）
├── metering/                      # ★ 新增：usage_ledger 计量 + Langfuse 插桩
│   ├── ledger.py                  # write-through 流水 + 聚合视图
│   └── observe.py                 # Langfuse/Sentry 初始化与装饰器
├── models/
│   ├── org.py                     # organizations/org_members/quotas/audit_logs
│   ├── team.py                    # teams/agents/agent_templates（预留 parent_team_id）
│   ├── team_task.py               # team_tasks/task_messages/task_runs/human_reviews
│   ├── memory.py                  # memories/knowledge_bases/kb_grants
│   ├── schedule.py                # schedules
│   └── usage.py                   # usage_ledger
├── routers/
│   ├── orgs.py                    # 组织/成员/配额/审计查询
│   ├── teams.py                   # 团队 CRUD + hire/fire + roster
│   ├── team_tasks.py              # 任务创建/详情/SSE 流/HITL 审批/取消
│   └── schedules.py               # 定时任务管理
└── (现有 skills/ tools/ services/ agents/ rag/ 不动)
```

依赖方向单向：`routers → team → skills/tools/services → models`。`team/` 内部：`runtime` 编排 `supervisor/worker`，二者只经 `mailbox` 通信，只经 `governor` 取上下文，只经 `permission` 用能力。

### 1.3 核心组件接口契约

```python
# team/runtime.py —— 对上层唯一入口（未来可替换执行引擎的抽象层）
class TeamRuntime:
    async def execute(self, task_id: UUID) -> TaskResult: ...
    async def interrupt(self, task_id: UUID, reason: str) -> None: ...
    async def resume(self, task_id: UUID, review_id: UUID, answer: dict) -> TaskResult: ...
    async def cancel(self, task_id: UUID, actor: ActorRef) -> None: ...

# team/mailbox.py —— Agent 间唯一通信原语
class Mailbox:
    async def post(self, task_id: UUID, msg_type: MsgType,
                   from_agent: AgentRef | None, to_agent: AgentRef | None,
                   content: str, refs: dict | None = None) -> int: ...   # 返回 seq
    async def read(self, task_id: UUID, agent_id: UUID, *, since_seq: int = 0) -> list[TaskMessage]: ...
    async def wait_for(self, task_id: UUID, agent_id: UUID,
                       msg_type: MsgType, timeout: float) -> TaskMessage: ...  # asyncio.Event 实现

# team/permission.py —— deny-by-default，Tool 入口 + dispatch 两处调用
class PermissionEngine:
    def effective_grants(self, agent: AgentRecord) -> Grants: ...   # grants ∩ 团队策略 ∩ 组织策略
    async def check_tool(self, agent: AgentRecord, tool_id: str,
                         args: dict) -> Decision: ...                # Decision{allow, reason, level}

# team/budget.py —— 四级继承：org → 根任务 → 子任务 → run
class BudgetService:
    async def precheck(self, *, task_id: UUID | None, org_id: UUID) -> BudgetStatus: ...
    def allocate(self, parent: BudgetSpec, share: float) -> BudgetSpec: ...  # dispatch 切分
    async def meter(self, run_id: UUID, model: str,
                    prompt_tokens: int, completion_tokens: int, cost_micros: int) -> None: ...

# team/governor.py —— 弹性上下文装配（统一 rag/context_pack.py 与 canvas 版 ContextPack）
class ContextGovernor:
    def assemble(self, agent: AgentRecord, task: TaskView,
                 *, token_budget: int) -> AssembledContext: ...
# AssembledContext{segments: list[Segment], dropped: list[SegmentKind], usage: int}
# Segment{kind, text, provenance}  —— provenance 沿用现有溯源头格式

# team/memory.py（Phase 2）
class MemoryStore:
    async def write(self, scope: MemoryScope, kind: MemoryKind,
                    content: str, *, importance: float,
                    expires_at: dt | None = None, source_run_id: UUID | None = None) -> UUID: ...
    async def search(self, scope: MemoryScope, query: str, *, k: int = 5) -> list[MemoryHit]: ...
    async def distill(self, agent_id: UUID) -> DistillReport: ...  # episodic → semantic
```

关键约束：

- `sup_tools.py` 中的 supervisor 工具是 **LLM tool-calling 的函数**，不走 ToolRegistry（它们改的是任务状态，不是数据访问）；hire/fire 保持人类 API 专属，MVP 不下放给 supervisor。
- Worker 不直接持有 `TeamRuntime` 引用——它收 dispatch 消息、产 report 消息，递归编排在 runtime 层（max_depth=1 在此强制）。

### 1.4 核心时序

**主链路（任务执行）**：

```
用户 → POST /teams/{id}/tasks
     → team_tasks(pending) + 根预算 + BackgroundTasks 启动 runtime.execute
Supervisor 循环（每轮 checkpoint 落 task_runs）:
  1. governor.assemble(supervisor)          # 共享块+roster+任务摘要+近K条信箱
  2. LLM(supervisor.agents_md + roster_card + budget_card, tools=sup_tools)
  3. dispatch(员工, 子任务, 子预算)
       → mailbox.post(DISPATCH) → per-agent 锁获取
       → worker: governor.assemble(员工) → SkillRunner.run_with_react
                 （工具面 = permission.effective_grants 过滤后的 Tool 集）
       → mailbox.post(REPORT, refs=artifact/used_*)
  4. supervisor 验收 → 下一轮 dispatch / request_human / finalize
finalize → generation_outputs（含溯源）→ task completed → SSE done
```

**HITL 暂停/恢复**：

```
request_human(question, options)
  → task_runs.interrupt_json = {review_id, question, options}
  → team_tasks.status = waiting_human → SSE hitl_request → BackgroundTask 结束（不占进程）
用户审批 POST /tasks/{id}/reviews/{rid}
  → human_reviews 落库 + audit_logs → runtime.resume(task_id, review_id, answer)
  → 从最近 checkpoint 重建 supervisor 上下文（信箱回放 + interrupt 注入）→ 循环继续
```

**崩溃恢复**：进程重启后启动扫描 `task_runs.status=running 且 心跳超时` → 状态回退到最近 checkpoint，`team_tasks` 重新入队（BackgroundTasks 丢失的任务由 DB 状态兜底，这是相对现状「重启丢任务」的增强）。

### 1.5 API 与 SSE 协议

**REST（挂 /api/v1，沿用现有鉴权）**：

| 方法 & 路径 | 说明 | 权限 |
|---|---|---|
| `GET/POST /orgs/{org_id}/members` | 组织成员管理 | owner/admin |
| `GET/PATCH /orgs/{org_id}/quotas` | 配额查看/调整 | owner/admin（平台侧管控） |
| `GET /orgs/{org_id}/audit` | 审计查询（action/agent/时间过滤，分页） | owner/admin |
| `GET /orgs/{org_id}/usage` | 用量账单（按团队/角色/月聚合） | 全员（member 看自己团队） |
| `POST /orgs/{org_id}/teams`、`GET /teams/{id}` | 建团队 / 详情（roster+共享块+预算余量） | org 成员 |
| `POST /teams/{id}/agents` | hire（agent_spec 或 template_id 克隆） | owner/admin |
| `PATCH /teams/{id}/agents/{aid}` | 改配置（persona/agents_md/grants/model） | owner/admin |
| `DELETE /teams/{id}/agents/{aid}` | fire（软删，body 带 reason） | owner/admin |
| `POST /teams/{id}/templates`、`GET /orgs/{id}/templates` | 角色模板：保存当前角色为模板 / 列表 | org 成员 |
| `POST /teams/{id}/tasks`、`GET /teams/{id}/tasks` | 下任务 / 任务列表 | org 成员 |
| `GET /tasks/{id}` | 详情：信箱时间线 + runs + 产物 + 预算消耗 | org 成员 |
| `GET /tasks/{id}/stream` | SSE 任务流（见下） | org 成员 |
| `POST /tasks/{id}/reviews/{rid}` | HITL 审批 `{choice, comment}` | owner/admin |
| `POST /tasks/{id}/cancel` | 取消任务（= kill switch L1） | owner/admin |
| `GET/POST/PATCH /teams/{id}/schedules` | 定时任务管理（Phase 2） | owner/admin |

**SSE chunk 协议扩展**（在 `agents/base.py` 现有 chunk 体系上新增，格式不变）：

| type | data | 说明 |
|---|---|---|
| `agent_message` | `{from, to, msg_type, seq, text}` | 信箱消息实时镜像（前端时间线） |
| `task_status` | `{status, round, budget_pct}` | 状态/轮次/预算水位 |
| `hitl_request` | `{review_id, question, options}` | 需人工决策 |
| `roster_change` | `{event: hire\|fire, agent}` | 成员变动广播 |
| `budget_warning` | `{level: 80\|100, scope}` | 预算预警 |

### 1.6 数据分类与租户边界（Tool 层 ACL 的分类依据）

| 类别 | 表 | 归属 | 隔离策略 |
|---|---|---|---|
| **平台共享知识资产** | cases / sop_workflows / prompt_templates / proposal_templates / technical_rules / quality_rules / visual_styles | 平台（管理后台维护） | 全租户只读，按行业/场景过滤，**不加 org_id** |
| **租户资产** | teams / agents / agent_templates / knowledge_bases / documents / canvases / projects / conversations / generation_outputs / memories | 租户 | 全部带 `org_id`，Tool 层强制过滤 |
| **平台运营数据** | users / org_members / quotas / audit_logs / usage_ledger / app_settings | 平台 | 运营与合规专用，租户只读自己的切片 |

这是 Phase 0 迁移的范围依据：只给租户资产表加 `org_id`，知识资产表不动。

### 1.7 与现有系统的集成点

| 现有组件 | 集成方式 | 改动量 |
|---|---|---|
| `SkillRunner.run_with_react` | Worker 直接调用；`SkillContext` 增加透传 `task_id/run_id/actor`（溯源列已齐） | 小 |
| `LLMService` / `OpenAILLMService` | metering + Langfuse 插桩的唯一位置；`generate*` 返回值补 usage（OpenAI SDK 已有） | 中（所有调用方受益） |
| `conversation_service` 意图路由 | `react_intent.py` 的 skill 白名单改为运行时从 roster 生成（消除硬编码）；新增 `team_dispatch` 意图：自然语言下任务 → 创建 team_task；**@员工 fast-path**（正则 + roster 匹配，先于 LLM 意图分类，可行性方案 §4.13）→ `mode=direct` 任务直接执行 | 中 |
| `canvas_agent_orchestrator` | Phase 1 末 feature flag 灰度：包装为「内置策划团队」SOP（pipeline_stages manifest → dispatch 顺序），新旧路径共存直至切换 | 中 |
| `conversation_locks` | 模式复用于 per-agent 执行锁（新表 `agent_locks` 或同表加 scope_type） | 小 |
| SSE 基建（`sse_chunk`/`_StreamAccumulator`） | 直接扩展 chunk 类型；任务流持久化沿用消息镜像思路 | 小 |
| thread 体系（scope_type/scope_ref_id） | `scope_type` 枚举加 `team`：团队对话线程绑定到 team，作为轻量入口 | 小 |

### 1.8 部署视图与演进

```
MVP（Phase 0-1）：
  [docker-compose]
  api（uvicorn 单进程）── postgres（pgvector）
                       └─ langfuse（自托管，含 clickhouse/postgres 内部栈）
  sentry：自托管或 SaaS（仅堆栈，无 prompt，CN 环境优先自托管/GlitchTip）

Phase 2：
  api（web 入口进程） + worker（队列消费进程，同镜像不同入口）
  队列选型：procrastinator（Postgres，零新依赖）首选，arq（Redis）备选
  APScheduler 随 worker 部署（单实例），触发去重靠 schedules 行锁

Phase 3：
  按需：A2A 网关（对外暴露远程成员）、容器沙盒池（L2/L3 工具）
```

### 1.9 横切关注点

- **测试策略（TDD，沿用户工作流规范）**：内核四件套（循环/预算/信箱/权限）先写测试——`MockLLMService` 已存在，补一个 `ScriptedSupervisor`（按脚本返回 dispatch/finalize 决策）即可确定性地测全链路；SQLite 内存库跑集成测试（现有惯例）；预算熔断/HITL 状态机各一组状态转换表测试。
- **Feature flag**：`app_settings` 加 `team_runtime_enabled / canvas_team_wrap_enabled`，Phase 1 灰度切换 canvas 路径。
- **回滚**：新表全为增量，旧路径（单专家对话/canvas）在 flag 后面，任何阶段可整层关闭回退。

---

## 2. Phase 0 系统设计：多租户地基（~2 周）

**目标**：租户边界成立、审计可写、工具分级就位。无 TeamRuntime，不改用户可见行为。

### 2.1 DDL（alembic 020-022）

```
020_org_tables:
  organizations(id, name, settings_json, created_at)
  org_members(org_id FK, user_id FK, role owner|admin|member, status, joined_at,
              PRIMARY KEY(org_id, user_id))
  quotas(org_id FK UNIQUE, max_teams, max_agents_per_team,
         max_concurrent_tasks, monthly_token_budget_micros)
  audit_logs(id, org_id, actor_type, actor_id, action, target_type, target_id,
             decision, reason, context_json, created_at)   -- 按月分区
021_ownership_columns:
  租户资产表加 org_id FK + 索引（§1.6 清单：projects/conversations/documents/
  canvases/generation_outputs/...）
  data migration：为每个现有 user 建「个人组织」并回填 org_id
022_tool_sensitivity:
  ToolManifest 增加 sensitivity: L0|L1|L2（dataclass 字段 + 注册期校验：
  L2 工具必须声明 audit action 名）
```

### 2.2 代码改造点（文件级）

| 文件 | 改造 |
|---|---|
| `tools/base.py` | `ToolContext` 增加 `org_id/user_id/actor`；`execute()` 前统一调 `PermissionEngine.check_tool`（Phase 0 简化版：仅分级标记 + 审计写入，正式 ACL Phase 1） |
| `skills/base.py` / `runner.py` | `SkillContext` 透传 org/user；`_resolve_skill_db_id` 不变 |
| `core/security.py` + 依赖注入 | JWT claims 增加 `org_id 列表`；新增 `require_org_role(owner|admin)` FastAPI 依赖 |
| `main.py` lifespan | 组织服务初始化；启动时为无 org 的存量 user 补建个人组织（幂等） |
| 新 `routers/orgs.py` | 成员/配额/审计三个只读端点先行 |

### 2.3 验收测试

1. 双用户双组织：A 组织用户经 `knowledge_search` 检索不到 B 组织 documents（Tool 层过滤生效）。
2. 平台资产（cases/sop）全组织可读。
3. admin 可 hire 前置校验通过、member 被拒（403 + audit_logs 落 deny）。
4. 未声明 sensitivity 的 Tool 注册失败（防新增工具漏标）。

---

## 3. Phase 1 系统设计：团队 MVP（4-6 周）

**目标**：用户建团队、hire/fire、下任务，supervisor 调度员工产出带溯源 Artifact，预算与 HITL 生效。

### 3.1 DDL（alembic 023-025）

```
023_team_core:
  teams(id, org_id, owner_user_id, name, description,
        settings_json, parent_team_id NULLABLE预留, created_at)
  agents(id, org_id, owner_user_id, team_id FK, name, avatar,
         persona, agents_md, model_alias, temperature,
         tool_grants JSONB, skill_grants JSONB,
         seat_role supervisor|worker,          -- 部分唯一索引: team_id+seat_role WHERE supervisor AND status='active'
         status active|fired, memory_policy_json,
         max_context_tokens, version, hired_at, fired_at, fired_reason, created_at)
  agent_templates(id, org_id, owner_user_id, name, persona, agents_md,
                  tool_grants, skill_grants, model_alias, created_at)
024_task_tables:
  team_tasks(id, team_id FK, thread_id NULLABLE, title, goal,
             trigger user|schedule|agent|mention, status,
             mode supervisor|direct DEFAULT supervisor,   -- @直接执行 = direct（§4.13）
             budget_json, parent_task_id NULLABLE预留,
             result_artifact_id, created_by_user_id, created_at)
  task_messages(id, task_id, seq, from_agent_id, to_agent_id, msg_type,
                content, refs_json, created_at)   -- UNIQUE(task_id, seq)
  task_runs(id, task_id, agent_id, run_role, parent_run_id, status, step_no,
            checkpoint_json, interrupt_json, token_usage_json, trace_id,
            skill_execution_id, error, started_at, ended_at, heartbeat_at)
  human_reviews(id, task_id, run_id, question, options_json, status,
               responded_by, response_json, created_at)
  agent_locks(agent_id UNIQUE, holder, expires_at)  -- conversation_locks 同款
025_metering:
  usage_ledger(id, org_id, team_id, agent_id, task_id, run_id, model,
               prompt_tokens, completion_tokens, cost_micros, created_at)  -- 按月分区
  skill_executions 加 task_run_id FK（泛化关联）
```

### 3.2 内核组件设计要点

**TeamRuntime（runtime.py）**：
- 入口即开 root trace（Langfuse），`task_runs` 心跳字段每轮更新（崩溃恢复判据：`heartbeat_at` 超时 2×轮次间隔）。
- `execute` 内部 `while` 受 `budget.precheck` + `max_rounds` 双重门控；每轮末 `checkpoint`（supervisor 决策历史 + 预算水位 + roster 快照）。
- 恢复语义：`resume()` 从 checkpoint 重建 supervisor 上下文（信箱回放 + interrupt 答复注入），不从零重跑已完成轮次。

**Supervisor（supervisor.py）**：
- system prompt = `agents_md + roster_card（成员名/职责/能力自述）+ budget_card（剩余轮次/token/水位）+ SOP 绑定（可选，沿 sop_load 注入）`。
- 工具面（`sup_tools.py`）：`dispatch(member, subtask, sub_budget_share?)` / `consult(member, question)` / `request_human(question, options)` / `finalize(artifact_ref)` / `reassign(from, to, reason)`。
- 乒乓检测在 dispatch 处拦截：同 (member, subtask 主题哈希) 连续 2 次 → 拒绝并强制重新规划或升级。

**Worker（worker.py）**：
- 拿到 dispatch → `agent_locks` 获取 → `governor.assemble` → 调 `SkillRunner.run_with_react`（输入由 worker 从子任务包构建，工具面= effective_grants）→ 产 report（artifact 引用 + used_* 溯源 + 自评）→ 释放锁。
- L2 工具调用 → 强制转 HITL（worker 暂停等 `human_reviews`，复用 interrupt 机制，粒度到单工具调用）。
- **direct 直达路径**：`mode=direct` 的任务跳过 supervisor 循环，runtime 直接走 worker 单次执行；governor 装配增加「线程近 K 轮对话」段；report 写信箱（supervisor 抄送可见）后任务即完成，预算/权限/审计/HITL 全部照常。

**PermissionEngine（permission.py）**：正式版。effective_grants 三相交 + Tool 入口每次调用校验 + deny 落审计；dispatch 权限仅 supervisor（runtime 层硬编码，不依赖 prompt）。

**Metering（metering/）**：
- `OpenAILLMService` 内包一层：每次调用（含流式结束）write-through `usage_ledger` + Langfuse generation；价目表从 `app_settings` 读。
- `BudgetService.precheck` 在 supervisor/worker 每次 LLM 调用前执行，100% 硬停转 HITL。

**可观测（metering/observe.py）**：四个插桩点（§1.2 与可行性方案 §4.12.3）本期一次到位：`OpenAILLMService`（generation）、`SkillRunner`（span）、`Tool.execute`（span+权限）、`TeamRuntime`（trace/event）。

### 3.3 前端页面（apps/web）

| 页面 | 内容 |
|---|---|
| 团队工作台 | roster 卡片（在线/忙碌/ fired 灰显）、hire 向导（含模板克隆）、员工编辑器（persona/agents_md/grants/model 别名）、fire 确认（填 reason） |
| 团队对话视图 | 团队线程 + roster 侧栏（@自动补全、在线/忙碌状态）、@direct 执行流式回复、无 @ 时走 supervisor 路由提示 |
| 任务视图 | 信箱时间线（agent_message 流式渲染，@成员高亮）、runs 状态条、预算水位条、HITL 审批卡片（选项按钮）、产物预览（复用现有 Artifact 组件） |
| 组织管理 | 成员与角色、配额、审计查询、用量账单 |

### 3.4 验收（对应可行性方案 §5）

1. 3 人团队端到端：任务「给 X 公司出方案」→ 策划/视觉/导出被正确 @ → 产物含 used_cases/used_chunks 溯源。
2. 预算 100% 触发硬停 HITL；账单按团队/角色可查且与 usage_ledger 一致。
3. 未授权工具调用被拒 + audit_logs 可查；Langfuse 可见完整 trace 树。
4. `ScriptedSupervisor` 全链路单测 + 双组织隔离回归（Phase 0 用例不破）。
5. **@ 直接执行**：多轮团队对话中 @某员工 → 该员工直接执行并流式回复（回答衔接线程前文）；@不存在/fired 员工 → 澄清卡片；目标忙碌 → 排队提示；@多个员工 → 回退 supervisor 路由。direct 任务的信箱/预算/审计记录完整。
6. 灰度开关：`team_runtime_enabled` 关闭后现有单专家路径完全不受影响。

---

## 4. Phase 2 系统设计：记忆·定时·风控（3-4 周）

### 4.1 DDL 与组件

```
026_memory:
  memories(id, scope_type agent|team|task, scope_id, kind working_summary|episodic|semantic|shared_block,
           content, summary, embedding vector(1536), importance,
           expires_at, source_run_id, created_at)   -- (scope_type, scope_id, kind) 复合索引
  knowledge_bases(id, org_id, owner_user_id, name, visibility)
  documents.kb_id FK；kb_grants(kb_id, grantee_type, grantee_id, level)
027_schedule:
  schedules(id, team_id, cron_expr, prompt_template, input_json,
            enabled, last_run_at, next_run_at)
```

- **MemoryStore**：写入随 report 产生（episodic 摘要，worker 顺带完成）；`distill` 为独立后台 job（扫描完成任务 → LLM 蒸馏 episodic→semantic → 写 shared_block 需 supervisor 权限校验）；检索走 HybridRetriever（向量列复用 pgvector，与 knowledge_search 同底座不同 scope 过滤）。
- **ContextGovernor 统一**：`rag/context_pack.py` 与 canvas `_build_context_pack` 收敛到 `governor.py` 装配段（§4.6 分段降级）；旧两个入口改为调 governor 的兼容包装，一个迭代内删除分叉。
- **SchedulerService**：APScheduler AsyncIOScheduler + SQLAlchemyJobStore（主库）；触发 = 创建 `team_task(trigger=schedule)` 入同一 runtime；去重 = schedules 行 `SELECT ... FOR UPDATE` 抢占。
- **RiskEngine（risk.py）**：规则配置在 `app_settings`（RPM、消耗速率阈值、连续失败数）；执行点在 `BudgetService.precheck` 与 `SkillRunner` 失败路径；kill switch 三级 API（task cancel / agent suspend / org pause）+ 审计。
- **队列化**：`spawn_worker` 改投 procrastinator 任务（worker 进程消费）；SSE 不变（仍由 web 进程从信箱表推流）。

### 4.2 验收

1. 跨任务记忆：新任务询问上次结论，员工经 episodic→semantic 命中作答（评测用例固定 5 条）。
2. cron 日报：每日 09:00 自动产出到团队共享块 + Artifact。
3. 人为构造异常消耗（mock 快速烧 token）→ 自动挂起 + 通知 owner（飞书/邮件通道）。
4. 共享块写入仅 supervisor 权限路径可写；kb_grants 变更即时生效（无缓存泄漏）。

---

## 5. Phase 3 系统设计：深化（概要级，按需展开）

| 能力 | 设计要点 |
|---|---|
| 员工 p2p 协作 | `consult/handoff` 消息类型开放给 worker（max_depth 灰度到 2）；handoff = 任务子包在员工间转移（supervisor 抄送可见，保留验收权） |
| Agent 模板市场 | agent_templates 增加 `published` 状态 + org 可见性；hire 向导加市场页；模板带「能力自述卡」预生成 |
| ephemeral fork | dispatch 可声明 `parallel:N` → 克隆 N 个临时实例（ephemeral=true，不进 roster），产出合并写岗位共享知识后回收 |
| A2A 对外互联 | 网关进程暴露 A2A endpoint（agent card = roster 能力自述）；远程成员 = `agents` 表加 `remote_endpoint`，dispatch 走 A2A client，信箱协议不变（对内屏蔽远程差异） |
| 评估 harness | Langfuse datasets 定期采样 supervisor 路由轨迹 → 改版回归评分（路由准确率/预算效率/产物质检），CI 门禁 |
| 沙盒 L2/L3 | 子进程池执行代码/文件类工具（资源限额+网络白名单）；外部租户自定义工具进 per-org 容器 |
| 公司组织树 | 启用 `parent_team_id/parent_task_id` 预留列；dispatch 目标扩展部门；预算沿任务树分配（可行性方案对话中已论证，默认 2 层） |

---

## 6. 依赖与里程碑总览

| 里程碑 | 历时 | 新增依赖 | 关键外部件 |
|---|---|---|---|
| Phase 0 | ~2 周 | 无 | — |
| Phase 1 | 4-6 周 | `langfuse` SDK、`sentry-sdk[fastapi,sqlalchemy]`（无 langchain 依赖） | Langfuse 自托管栈（docker-compose） |
| Phase 2 | 3-4 周 | `apscheduler`、`procrastinator`（或 arq+redis） | 飞书/邮件通知通道（复用现有同步设计） |
| Phase 3 | 持续 | 视能力项：`a2a-sdk`、Docker 工具池 | 按需 |

每阶段出口条件 = 该节验收全绿 + 上一阶段回归不破（Phase 0 隔离用例为常驻回归集）。
