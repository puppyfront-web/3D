# AI 团队平台（用户自建多 Agent 团队）可行性与综合方案

> 日期：2026-10-23（2026-10-27 评审通过定稿）
> 状态：已定稿
> 范围：在现有「花生ONE」Skill/Tool 运行时之上，演进为用户可自建 AI 团队（hire/fire、Supervisor 调度、员工 A2A 协作、独立/共享记忆、定时任务、弹性上下文、HITL）的多租户平台

---

## 0. 结论（TL;DR）

**可行，且现有代码库已完成约 60% 的基础设施。** 推荐方案：

**自研「团队运行时内核」（Team Runtime），不引入 AutoGen / CrewAI / LangGraph 作为架构中心**，但显式借鉴三者的核心语义：

| 借鉴对象 | 借什么 |
|---|---|
| LangGraph | checkpoint 持久化 + interrupt/resume（HITL）+ 有界图执行 |
| MetaGPT | Environment（团队容器）+ 消息池发布订阅 + `hire()` 角色注入 |
| Letta (MemGPT) | memory blocks（私有块 + 共享块）三层记忆模型 |
| Google A2A 协议 | 任务生命周期状态机（submitted/working/input-required/completed/failed），仅在 Phase 3 对外互联时采用协议本身 |

核心理由（详见 §3）：

1. **产品形态与框架假设冲突**：AutoGen/CrewAI/LangGraph 均为「代码期定义 Agent/图」，而本产品要求「用户在 Web 界面动态创建团队、运行时 hire/fire」——DB 驱动的动态 Agent 是所有框架的短板，强行套用等于写一层翻译层再绕开框架的大部分能力。
2. **AutoGen 已停更并入 Microsoft Agent Framework**（2026-04 GA），现在选它等于接手一个迁移期资产。
3. **现有资产复用度高**：Skill/Tool 双层 + Manifest 注册、SkillExecution（已含 `agent_role`，注释自述"复用为 AgentRun 表"）、conversation_locks DB 互斥、SSE chunk 协议 + 流回放、metadata 信封状态恢复、HybridRetriever RAG、溯源列体系——这些正是多 Agent 平台最贵的部分。
4. **多租户、预算治理、记忆隔离是产品层问题**，没有任何框架替你解决。

翻盘条件（何时改用 LangGraph 做执行引擎）：当「时间旅行调试 / 重执行 / 复杂子图编排」成为刚需、且团队接受 langchain-core 依赖链时，在 `TeamRuntime.execute()` 抽象下替换实现（接口已预留，见 §4.2）。

---

## 1. 现状盘点：资产与缺口

### 1.1 可直接复用的资产

| 资产 | 位置 | 在新架构中的角色 |
|---|---|---|
| Skill/Tool 双层 + Manifest + pkgutil 自动发现 | `app/skills/registry.py`、`app/tools/registry.py` | 员工的「手脚」——Agent 只编排，能力仍走 Skill/Tool |
| SkillRunner + ReAct（max_turns、fallback_skill 前置校验） | `app/skills/runner.py:133` | 员工执行循环直接复用 |
| SkillExecution 表（`agent_role`/`node_ids`/used_* 溯源列） | `app/models/skill.py:74,114` | 泛化为 `task_runs`（或加 run 类型字段） |
| metadata 信封 `{"_agent","ctx"}` + thread 恢复 | `app/agents/base.py:75-97` | Agent 工作状态的持久化模式 |
| conversation_locks（唯一索引 + TTL + holder） | `app/services/conversation_lock_service.py` | 推广为 per-agent 执行互斥（一个员工同一时刻只跑一个任务） |
| SSE chunk 协议 + `_StreamAccumulator` 回放 | `app/agents/base.py:35-50` | 团队任务流的传输层（扩展 `agent_message` chunk 类型） |
| 独立 session 隔离模式（SQLite 防死锁） | `conversation_service.py:774-844` 等 | 并行员工执行的 DB 并发基础 |
| SOPWorkflow.pipeline_stages manifest 门控 | `canvas_agent_orchestrator.py:488-522` | 「配置驱动流水线」雏形 → 团队 SOP 模板 |
| 两套 Context Pack（prompt 渲染 + 溯源 dict） | `rag/context_pack.py`、`_build_context_pack` | 统一为 ContextGovernor（§4.6） |
| LLMService 工厂 + DB 动态配置 | `services/llm_service.py:310` | per-agent 模型路由（supervisor 可用轻模型） |
| HybridRetriever + pgvector | `rag/retriever.py` | 记忆/知识库统一检索底座 |
| 版本树（视觉概念图/画布） | project_versions 等 | Artifact 版本管理沿用 |

### 1.2 缺口（必须新建）

1. **Agent 不是一等实体**：无 `agents` 表；「专家角色」硬编码在 canvas orchestrator 私有方法和 prompt 字符串里。
2. **无团队/组织层**：全库无 tenant/org；`SkillExecution.user_id` 常为 None——多租户是前置必改项。
3. **无任务队列**：BackgroundTasks 单进程、120s 超时、重启丢任务。
4. **无长期记忆**：上下文 = 最近 50 条消息重建；无摘要压缩、无跨会话沉淀。
5. **无 Agent 间通信**：只能靠调用链传参，无信箱/消息总线。
6. **无 scheduler**：全库无任何 cron 实现。
7. **意图路由白名单硬编码**：新增员工角色需改 4-5 处代码（`react_intent.py:45-51` 等）。

---

## 2. 竞品与开源方案分析

### 2.1 产品竞品（验证方向，非直接可抄）

| 竞品 | 关键事实 | 对本方案的启示 |
|---|---|---|
| **Coze 3.0（扣子）** | 2026-05/06 发布「多人 + 多Agent」混编团队模式，支持接入 Claude Code 等本地 Agent；宣称 1 亿+ Agent 在运行；**开源版（Apache 2.0）不含 Multi-Agent 协作**——那是商业版卖点 | 最强产品验证：方向成立、市场已被教育；但核心能力闭源 → 自建有空间。参考其「资产自动沉淀、项目独立」的团队工作区交互 |
| **Dify** | Agentic Workflow + RAG 平台，多智能体靠 Agent 节点串工作流，非自由组队 | 定位差异：Dify 是「工作流优先」，本产品是「角色/组织优先」（更接近 Coze 团队模式 + MGX）。RAG 管道做法可参考 |
| **MGX（MetaGPT X）** | 2025-02 发布，定位「第一个 AI agent 开发团队」产品 | 证明 MetaGPT 公司隐喻可以产品化；其 hire/dispatch 交互值得体验 |
| **ChatDev / MetaGPT** | 学术开源，`Environment.add_agents` + 角色订阅消息池 | 借语义不借代码：研究型代码库不适合多租户 Web 产品 |
| **GPTs / Copilot @mention** | 微软 Teams 中 @agent 路由 | 「@员工」交互的心智模型来源 |

### 2.2 框架横评（2026-10 现状）

| 维度 | LangGraph | AutoGen → MS Agent Framework | CrewAI | MetaGPT | **自研内核（推荐）** |
|---|---|---|---|---|---|
| 定位 | 显式状态图，生产控制最强 | AutoGen 2026-04 起并入 Microsoft Agent Framework（GA），处于迁移期 | 角色任务列表，快速原型 | SOP 软件公司隐喻 | DB 驱动动态团队 |
| Agent 定义方式 | **代码期编译图** | 代码期 | 代码期 Crew/Task | 代码期 Role 类 | **DB 运行时（hire/fire 即 CRUD）** ✓ |
| HITL | `interrupt()` + checkpointer，业界最佳 | 有 Handoff/审批，较散 | callback 钩子 | 弱 | 自实现（语义抄 LangGraph） |
| 持久化执行 | Checkpointer（SQLite/Postgres）成熟 | 有 | 弱 | 弱 | task_runs + checkpoint JSON |
| 多租户/预算/记忆隔离 | 不解决 | 不解决 | 不解决 | 不解决 | 产品层自建（无捷径） |
| 与现有运行时融合 | 需重写 SkillRunner/锁/SSE 为其惯用法 | 同左，且迁移风险 | 融合浅但能力也浅 | 不可融合 | **零翻译成本** ✓ |
| 依赖风险 | langchain-core 版本churn；核心 MIT 免费（Platform/Cloud 才收费） | AutoGen 停更，MSAF .NET 侧更成熟 | 商业化摇摆（企业版分叉） | 维护放缓 | 自负（内核收敛约 2-3k 行） |
| 结论 | 执行引擎备胎（§4.2 预留接口） | ✗ 排除 | ✗ 排除（可做内部实验） | ✗ 排除（借语义） | ✓ 采用 |

> 附：Google **A2A 协议**（v1.0，2026）定位是**跨平台不透明 Agent 互联**——本产品员工协作在进程内，用协议本身是过度设计；但其**任务生命周期状态机**（submitted → working → input-required → completed/failed）值得直接采用为 `team_tasks.status` 语义。LangSmith Agent Server、IBM watsonx、Azure Foundry 均已支持 A2A，Phase 3 对外互联时再引入。

---

## 3. 选型决策详述：为什么自研内核

1. **动态性冲突是根本矛盾**。用户在管理界面创建员工（性格 + agents.md + 知识库授权 + 工具授权），运行时 hire/fire。三大框架的 Agent/Crew/Graph 都是 Python 代码对象，动态组装要么走"模板代码 + 参数注入"（丢失框架的图校验价值），要么每次 hire 后热编译图（LangGraph 支持但语言惯用法相悖）。现有 canvas orchestrator 的教训已经证明：硬编码流水线 + 框架惯用法 = 双重维护。
2. **要抄的东西边界清晰、量可控**。真正需要自研的只有四件：① 有状态任务循环 + checkpoint（≈ 500 行）；② interrupt/resume（waiting_human 状态 + 恢复入口，现有 agent-runs 轮询模式已验证同构方案，≈ 300 行）；③ 信箱（一张表 + seq，≈ 200 行）；④ 记忆块（一张表 + 检索 + 蒸馏 job，≈ 500 行）。相比引入框架后重写现有 SkillRunner/锁/SSE/执行记录的迁移成本，自研更便宜。
3. **现有代码的架构判断与此一致**。仓库已有两次明确决策记录："no Redis queue in MVP"（`canvas_agent_orchestrator.py:38-40`）、"Reuses SkillExecution as the AgentRun table"（`models/skill.py`）——演进方向本来就是运行时自持。
4. **框架的真正价值（可观测、重执行、生态节点）** 通过两个动作保留：TeamRuntime.execute 抽象（可替换为 LangGraph 引擎）；评估/观测直接复用 SkillExecution 溯源 + retrieval_logs。

---

## 4. 目标架构设计

### 4.0 总览

```
用户 ──> 团队工作区（Web）
          │  hire/fire、下发任务、HITL 审批、定时任务管理
          ▼
┌─────────────────────────────────────────────────────┐
│ Team Runtime（新增，进程内）                          │
│  ┌───────────┐   dispatch/report    ┌────────────┐  │
│  │Supervisor │<────────────────────>│ Worker × N  │  │
│  │(规划/分配/ │   信箱 task_messages │ (ReAct 循环  │  │
│  │ 验收/升级) │                      │  复用SkillR.│  │
│  └─────┬─────┘                      └─────┬──────┘  │
│        │ checkpoint/interrupt             │          │
│  ┌─────▼──────────────────────────────────▼───────┐ │
│  │ task_runs（执行记录+状态快照） │ memories（三层）│ │
│  └────────────────────────────────────────────────┘ │
│  ContextGovernor（弹性上下文装配，统一两套 ContextPack)│
└───────────────────┬─────────────────────────────────┘
                    │ 沿用
        ┌───────────▼────────────┐
        │ Skill / Tool 层（现有） │  知识库/RAG/web_search/导出…
        └────────────────────────┘
```

设计原则：**Agent 层只做「组织与编排」，能力一律走现有 Skill/Tool 层；数据一律落库可溯源**（延续 AGENTS.md §2.2/§4.2 约束）。

### 4.1 领域模型（新增/改造表）

```
organizations(id, name, settings_json, created_at)          -- 租户=组织
org_members(id, org_id, user_id,                            -- 人类成员及组织内权限
            role: owner|admin|member, status, joined_at)    -- hire/fire、HITL 审批按此控权
quotas(id, org_id, max_teams, max_agents_per_team,
       max_concurrent_tasks, monthly_token_budget)           -- 平台保护，runtime 强制执行
audit_logs(id, org_id, actor_type: user|agent|system, actor_id,
           action, target_type, target_id,
           decision: allow|deny, reason, context_json, created_at)  -- 只增不改的安全审计流
usage_ledger(id, org_id, team_id, agent_id, task_id, run_id, model,
             prompt_tokens, completion_tokens, cost_micros, created_at)  -- token 计量流水，聚合出账单
teams(id, org_id, owner_user_id, name, description,
      settings_json{max_rounds, token_budget, deadline_default, shared_blocks[]},
      created_at)                                   -- 租户边界=org_id；owner_user_id 仅记创建者（审计）
agents(id, org_id, owner_user_id, team_id,  -- 角色实例只属于一个团队，不跨团队共享
       name, avatar,
       persona            TEXT,     -- 性格描述（喂入 system prompt）
       agents_md          TEXT,     -- 系统提示词（用户上传/编辑）
       model_alias, temperature,    -- per-agent 模型路由
       tool_grants[], skill_grants[],   -- 权限白名单
       seat_role: supervisor|worker,    -- 每团队恰好一个在岗 supervisor（部分唯一索引保证）
       status: active|fired,            -- hire/fire 即此状态机（软删，保留审计）
       memory_policy_json{episodic_ttl, distill_enabled},
       max_context_tokens, version,
       hired_at, fired_at, fired_reason, created_at)
agent_templates(id, org_id, owner_user_id, name, persona, agents_md,
                tool_grants[], skill_grants[], model_alias)  -- 复用发生在模板层（克隆 hire），不共享实例
knowledge_bases(id, org_id, owner_user_id, name, visibility: private|team)
  └─ documents/document_chunks 增加 kb_id（复用现有 RAG）
kb_grants(kb_id, grantee_type: agent|team, grantee_id, level: read)
memories(id, scope_type: agent|team|task, scope_id,
         kind: working_summary|episodic|semantic|shared_block,
         content, summary, embedding, importance,
         expires_at, source_run_id, created_at)
team_tasks(id, team_id, thread_id?, title, goal,
           trigger: user|schedule|agent,
           status: pending|running|waiting_human|completed|failed|cancelled|timeout,  -- A2A 语义
           budget_json{max_rounds, max_tokens, max_depth, deadline},
           result_artifact_id, created_by_user_id)
task_messages(id, task_id, seq,
              from_agent_id|null(用户/系统), to_agent_id|null(广播),
              msg_type: dispatch|report|consult|hitl_request|hitl_response|system,
              content, refs_json, created_at)       -- 信箱（MetaGPT 消息池的 SQL 化）
task_runs(id, task_id, agent_id, run_role: supervisor|worker,
          parent_run_id, status, step_no,
          checkpoint_json, interrupt_json,
          token_usage_json, trace_id,               -- langfuse trace_id，跨进程/队列恢复后仍归同一 trace
          skill_execution_id,                       -- 关联现有执行明细
          error, started_at, ended_at)
human_reviews(id, task_id, run_id, question, options_json,
              status: pending|approved|rejected|expired,
              responded_by, response_json)
schedules(id, team_id, cron_expr, prompt_template, input_json,
          enabled, last_run_at, next_run_at)        -- 定时任务
```

要点：
- **租户=组织**：MVP 期每个注册用户自动创建一个「个人组织」（个人空间），企业租户通过 `org_members` 邀请成员共享团队——两级场景同一套模型，后续无需回刷表结构。`owner_user_id` 统一降级为「创建者」审计字段，隔离边界只看 `org_id`。
- **角色单团队归属**：`agents.team_id` 外键直接绑定，`team_members` 关联表取消——roster 即 `agents WHERE team_id=? AND status='active'`；同一个人设要在多个团队使用，走 `agent_templates` 克隆出独立实例（各自积累记忆）。隔离链 `org → team → agent` 单向干净，per-agent 执行锁也不存在跨团队争用。
- `task_runs` 与现有 `SkillExecution` 一对多关联，不推倒重来；溯源列体系（used_cases/used_chunks/used_external_sources）天然适用于团队产物。
- `memories` 一张表三种 scope，靠 `scope_type` 隔离，检索层强制过滤（§4.5）；角色单团队归属后 `scope_type='agent'` 无跨团队歧义。

### 4.2 Supervisor 调度循环（核心，MetaGPT 式）

```python
async def run_team_task(task: TeamTask):
    run = create_supervisor_run(task)
    while True:
        if task.round >= budget.max_rounds:      # 轮次熔断
            return await escalate_or_fail(task, reason="max_rounds")
        ctx = governor.assemble(supervisor, task)  # §4.6
        decision = await llm_call(
            system = supervisor.agents_md + roster_card(team) + budget_card(task),
            tools  = [dispatch, consult_member, request_human, finalize, reassign])
        match decision:
          case Dispatch(member, subtask, sub_budget):
                mailbox.post(DISPATCH, member, subtask)
                worker_run = spawn_worker(member, subtask, sub_budget)  # 每 agent 一把执行锁
                report = await wait_report(worker_run, timeout)         # 崩溃→checkpoint 恢复
          case Consult(member, question):        # 非阻塞问答，不占轮次
                ...
          case RequestHuman(question, options):  # HITL：挂起+通知+可恢复
                run.checkpoint(); task.status = waiting_human
                await notify_user(task); return await resume_later()
          case Finalize(artifact):               # 产物走 generation_outputs，含溯源
                return complete(task, artifact)
        run.checkpoint()                          # 每轮持久化，进程重启可续跑
```

Worker 循环 = 收 dispatch → ContextGovernor 装配私有上下文 → **复用 `SkillRunner.run_with_react` 执行**（工具面 = `tool_grants` 过滤后的 Tool 集）→ 写 report（含 artifact 引用与 used_* 溯源）→ 写 episodic 记忆。

**关键约束**：
- **默认 `max_depth=1`**：员工不能再派发子任务（MetaGPT 式递归团队是后期开关）；员工间协作走 `consult`（问答）与 supervisor 中转的 `handoff`。
- **per-agent 并发 = 1**：一把 `conversation_locks` 同款互斥锁，员工「正在忙」时 supervisor 的 dispatch 进入等待队列——防止 SQLite/Postgres 写冲突与上下文串扰。
- TeamRuntime 对外只暴露 `execute(task) / interrupt(task) / resume(task, answer)` 三个方法——**未来可整体替换为 LangGraph 引擎**而不动上层。

### 4.3 hire / fire 设计

```
hire(team_id, agent_spec{persona, agents_md, model, grants} | template_id)
  → 写 agents(team_id, status=active)          -- 实例只属于本团队；模板=克隆出全新实例
  → 信箱注入 system 消息：「新成员 <name> 入职，能力自述：<skill_grants 摘要>」
  → supervisor 下一轮 roster_card 自动包含该成员
fire(team_id, agent_id, reason)
  → agents.status=fired（软删，历史消息与 run 记录保留审计）
  → 该成员执行锁立即失效；运行中任务在下一 checkpoint 检查点重分配或降级
  → 信箱注入 system 消息；supervisor 后续 roster 不再含该成员
```

**复用走模板层，不共享实例**：同一「策划专家」人设被两个团队使用 = 各自克隆一份，独立积累 episodic 记忆——这符合直觉（两个团队的策划专家经验本来就该不同），也让记忆隔离、知识库授权、执行锁都天然按团队收口，不存在「同一实例在两个团队并发执行」这类状态串扰问题。

入职引导（可选增强）：hire 后自动让新员工跑一次「能力自述」 Skill，产出 roster 中的描述卡——supervisor 路由质量主要取决于 roster 描述质量，这一步性价比极高。

### 4.4 Loop 上限与熔断矩阵

| 机制 | 默认值 | 触发后行为 |
|---|---|---|
| `max_rounds`（supervisor 派发轮次） | 8（硬上限 16） | 超出 → HITL 升级（附最近决策摘要），人工选「续 4 轮 / 终止」 |
| `max_depth`（派发层级） | 1 | 员工工具面不含 dispatch |
| `max_tokens`（任务级预算） | 按团队 settings | 80% 预警注入 supervisor 上下文；100% 强制 finalize 或升级 |
| `deadline`（墙钟） | 30min | timeout 终态 + checkpoint 存档 |
| 乒乓检测 | 相邻轮 dispatch 同一成员同主题 ≥2 次 | 强制 supervisor 重规划或升级人工 |
| 失败升级 | 同一子任务连续失败 2 次 | 复用 ReAct `_reflect` 结论（ask_user/give_up）映射为 HITL |
| per-agent 并发 | 1 | 排队，防状态串扰 |

### 4.5 记忆：三层 + 共享/隔离（Letta memory blocks 语义）

| 层 | 存储 | 生命周期 | 隔离 |
|---|---|---|---|
| working（工作记忆） | task_runs.checkpoint_json | 任务期间 | 任务级 |
| episodic（情景记忆） | memories(episodic) + 向量化 | TTL（默认 30 天，可配） | **agent 私有**，检索强制 `scope_type='agent' AND scope_id=me` |
| semantic + shared_block（语义/共享块） | memories(semantic/shared_block) | 长期 | 共享块 **team 级**，写权限仅 supervisor（或受权员工）；读全团 |

- **沉淀路径**：任务完成时异步「蒸馏 job」把 episodic 摘要为 semantic 事实（复用 LLMService.generate_json）。
- **知识库 ≠ 记忆**：用户上传资料走 `knowledge_bases + kb_grants + RAG`（给定的事实），记忆是员工工作中习得的事实。两者在 ContextGovernor 中分槽装配、分别溯源。
- **隔离的实现是检索层 ACL**：`knowledge_search` Tool 增加 `kb_grants` 过滤（现在无租户概念，Phase 0 必改），memories 查询强制 scope 谓词。工具层是唯一数据入口（现有架构约定），ACL 收口于此。

### 4.6 弹性上下文：ContextGovernor

统一现有两套 Context Pack（prompt 渲染器 + 溯源 dict），按 `max_context_tokens` 预算装配，超限逐级降级：

```
[固定段] persona + agents_md + roster_card + budget_card     —— 不降级
[共享块] team shared_blocks 快照                              —— 压缩为标题
[任务段] 任务目标 + 计划 + 当前子任务包                        —— 摘要化
[信箱段] 最近 K 条消息原文，更早的折叠为轮次摘要               —— 先降级
[检索段] 私有 episodic RAG + 授权 KB RAG + web 来源           —— 按 importance 截断
```

每段保留溯源头（沿用 ContextPack `to_prompt()` 的分段标记），产物侧继续落 used_* 列。

### 4.7 HITL 设计

- **主动中断**：supervisor `request_human` / 员工 ReAct 判定 `ask_user` → `task_runs.interrupt_json` 记录问题与选项 → `team_tasks.status=waiting_human` → SSE `hitl_request` chunk + 站内通知 → 用户在团队工作区作答 → `resume()` 从 checkpoint 恢复（语义对齐 LangGraph `interrupt()/Command(resume=...)`，但持久化在自己的 task_runs 表）。
- **强制触发**（不可绕过）：预算 80%/100%、高危动作（export 导出、对外发送、写共享块）、失败升级、乒乓检测。
- **沿用现有产品规则**：AGENTS.md §6.3 的四类人工审核节点（企业画像确认/策划案审核/视觉确认/导出前检查）映射为标准 HITL 卡片类型，团队模式下同样生效。

### 4.8 定时任务

- `schedules` 表 + **APScheduler（AsyncIOScheduler + SQLAlchemyJobStore 复用主库）**。
- 触发动作 = 创建 `team_task(trigger=schedule)` 进入同一 Supervisor 循环——不做独立定时执行路径（一套状态机）。
- 多实例部署防重复触发：复用 conversation_locks 的 DB 唯一索引互斥模式（`schedules.id + 时间片` 为锁键）；单实例 MVP 下无此问题。
- 产物按任务送达团队工作区 + 可选通知渠道（复用飞书同步设计的通道，见 `2026-06-09-feishu-session-sync-design.md`）。

### 4.9 任务队列演进

- **MVP（单实例）**：维持 BackgroundTasks + DB 状态轮询（agent-runs 模式已验证），但 task_runs.checkpoint 保证重启后可从最近检查点续跑（解决现状「重启丢任务」）。
- **Phase 2（并行压力出现时）**：引入 **arq（Redis）** 或 **procrastinator（Postgres）**——团队已明确 Postgres 为生产库，后者零新依赖；把 `spawn_worker` 投递改为队列投递即可，TeamRuntime 接口不变。

### 4.10 安全与多租户（Phase 0 前置）

1. **ownership 贯穿（组织级）**：teams/agents/agent_templates/knowledge_bases 全部带 `(org_id, owner_user_id)` 双列，隔离边界为 `org_id`；Tool 层入口统一校验（现有 Tool 无租户概念，必须先改，否则「独立记忆/知识库」是空谈）。hire/fire、团队设置变更、HITL 审批的权限由 `org_members.role` 控制（owner/admin 可管理，member 只能用）；`quotas`（团队数/每团队角色数/并发任务/月度 token）在 runtime 强制执行，防平台级滥用。
2. **agents.md 是用户可控的系统提示词** = 最大注入面：工具白名单（`tool_grants`）硬收口，高危工具（export/web_search/写共享块）默认不授予；工具输出以 untrusted 段标记注入（沿 web_search 边界 spec 的思路）。
3. **预算即 DoS 防线**：token/轮次/时长三维预算在 runtime 强制执行，不依赖 LLM 自觉。
4. **审计**：安全相关事件统一落 `audit_logs`（§4.11），领域过程记录仍走 `task_messages(system)` 与 `human_reviews`，满足「引用可追溯」既有规范。

### 4.11 审计、权限、沙盒与 Token 风控

#### 4.11.1 统一审计日志

`audit_logs` 只增不改（append-only），覆盖四类事件，统一由 runtime 与 Tool 层写入：

| 事件类 | 示例 |
|---|---|
| 权限决策 | 工具调用的 allow/deny（含拒绝原因）、kb_grants 校验失败 |
| 组织变更 | hire/fire、org 成员变动、配额调整、kill switch 操作 |
| 高危动作 | L2 工具触发（export/外发/写共享块）、HITL 请求与审批结果 |
| 风控事件 | 预算触顶、限速、异常熔断、沙盒越界（超时/注入特征） |

查询场景三个入口：按 org（合规审查）、按 agent（绩效复盘）、按 task（问题回溯）。热数据保留策略（如 180 天）+ 分区，防表膨胀。

#### 4.11.2 三层权限模型（deny-by-default，决策点收口两处）

| 层 | 主体 | 控制什么 | 载体 |
|---|---|---|---|
| 人的权限 | 人类用户 | org 管理 / hire / fire / HITL 审批 / 配额与密钥配置 | `org_members.role` 动作矩阵 |
| 能力权限 | Agent | 可用 Tool/Skill 白名单、dispatch 权（仅 supervisor） | `tool_grants` / `skill_grants` |
| 数据权限 | Agent | 知识库、记忆 scope、Artifact 可见性 | `kb_grants` + 检索层 ACL |

- **工具敏感度分级**（Tool Manifest 增加标签，注册期静态校验）：
  - `L0 只读`：case_search / knowledge_search / sop_load —— 授权即可用
  - `L1 计费`：image_generate / web_search —— 授权 + 计量 + 速率限制
  - `L2 副作用`：export、写共享块、对外发送 —— 授权 + **强制 HITL** + 审计
- **生效权限计算**：dispatch 时 runtime 计算 `effective_grants = agents.grants ∩ 团队策略 ∩ 组织策略`，注入 SkillContext；Tool 每次调用重新校验（不信任缓存），拒绝即落 `audit_logs`。

#### 4.11.3 沙盒：能力边界 + 分级隔离

本架构的天然优势：**Agent 没有原生算力**——不能执行代码、不能开 socket、不能碰文件系统，一切经 Tool 层中转，不存在「任意代码执行」攻击面。沙盒按引入新工具的风险分三级：

| 级别 | 时机 | 机制 |
|---|---|---|
| L1 进程内边界（MVP） | 现有工具集 | Tool 超时与取消（复用 120s 兜底模式）；凭证隔离——API key 只存在于 provider 层，LLM 上下文只见工具结果，永不进 prompt；`agents_md` 与工具输出按 untrusted 段标记 + 指令层级（system 指令 > 工具输出内容），沿 web_search 边界 spec 思路；文件访问仅限 artifact store |
| L2 子进程池（Phase 2） | 引入代码执行/文件类工具时 | 独立进程 + 资源限额（CPU/内存/时长）+ 无共享 DB session + 网络域名白名单 |
| L3 容器隔离（Phase 3） | 对外租户自定义工具 | per-org 容器（Docker 级），工具产物经扫描后入 artifact store |

每次越界行为（超时、调用未授权工具、注入特征命中）→ `audit_logs` + 按频率升级（3 次/任务 → agent 自动 suspend）。

#### 4.11.4 Token 管理与风控

**计量**：每次 LLM 调用 write-through 到 `usage_ledger`（run 级精度：org/team/agent/task/run/model/tokens）；模型价目表配置化（`app_settings`），`cost_micros` 统一微元单位，避免浮点漂移。成本分摊报表（每团队/每角色/每月）做成定时任务产出——用自己的团队跑自己的运营报表。

**预算层级**（四级继承，全部 runtime 强制）：

```
org 月度 quota（quotas.monthly_token_budget）
  └─ 根任务预算（team_tasks.budget_json.max_tokens）
       └─ 子任务分配（dispatch 到部门时切分，§4.11 前述预算继承）
            └─ 单 run 上限（task_runs 级硬顶）
```

- LLM 调用前预检余额；任务级 80% 预警注入 supervisor 上下文（§4.4 已有），100% 硬停进入 HITL；org 级触顶 → 新任务拒绝、运行中任务完成当前 step 后挂起。
- **风控规则**（规则引擎化，初始四条）：
  1. 速率限制：org 级 RPM / 并发 run 数上限
  2. 异常消耗：滑动窗口内消耗速率超阈值（如 10 分钟烧掉日预算 50%）→ 自动挂起 + 通知 owner/admin
  3. 失败熔断：同一 run 连续 N 次 LLM/工具失败 → 终止并升级（复用 ReAct 反思结论）
  4. kill switch 三级：任务取消 / agent suspend / org 暂停——管理台一键，全部落审计
- **透明度**：用户随时可见余额、消耗明细、当前挂起原因；告警走 HITL 通知通道（邮件/飞书）。

### 4.12 可观测性体系（Langfuse + Sentry + 自有审计分层）

#### 4.12.1 分层职责：每个关注点只有一个真相源

| 层 | 关注点 | 载体 | 保留期 | 谁用 |
|---|---|---|---|---|
| 业务审计 | 谁对谁做了什么（合规/追责） | `audit_logs`（§4.11.1） | 长期，分区归档 | 管理员/合规 |
| 计量计费 | token 消耗与成本分摊 | `usage_ledger`（§4.11.4） | 永久（按月聚合预结算） | 用户/财务 |
| LLM 可观测 | 轨迹、延迟、prompt 调试、评估数据集 | **Langfuse 自托管** | 30-90 天 | 研发/运营 |
| 应用可观测 | 异常、性能、崩溃 | **Sentry**（自托管或 SaaS） | 90 天 | 研发 |
| 应用日志 | 排障上下文 | 结构化 JSON 日志（注入 correlation ID） | 按日志栈 | 研发 |

三条硬规则：

1. **计费只认 `usage_ledger`**——Langfuse 的成本视图仅作调试参考，不作为扣费依据（两家对 usage 的口径和完整性承诺不同）。
2. **互链不复制**：Sentry 事件带 `task_id/run_id` tag，Langfuse trace 带 `task_id`，audit_logs 事件带 `trace_id`——任一入口都能 30 秒跳转到完整上下文，数据不双写。
3. **降级安全**：Langfuse/Sentry 挂掉不影响主流程（异步缓冲、失败静默记数）——沿用 web_search 降级原则，可观测组件自己不能成为故障源。

#### 4.12.2 追踪模型：Langfuse trace 树 = 任务树

```
Trace: team_task（id=team_task_id；metadata: org_id/team_id/trigger/budget）
 └─ Span: task_run（agent_id, seat_role, supervisor 第 N 轮）
     ├─ Generation: 每次 LLM 调用（model, prompt, completion, usage, 延迟, TTFT）
     ├─ Span: skill_execution（skill_id, execution_id, ReAct 重试/fallback 标记）
     │    └─ Span: tool call（tool_id, 耗时, allow/deny, L0/L1/L2 敏感度）
     ├─ Span: worker run（子任务，结构同构递归）
     └─ Event: HITL 请求/恢复、预算 80% 预警、熔断触发
```

- **跨边界续接**：`task_runs.trace_id` 持久化 langfuse trace id；worker 从队列拉起、定时任务触发、崩溃恢复三种场景都从该列 rehydrate 上下文，span 始终归入同一 trace。
- 进程内用 contextvars 传播（asyncio 安全），TeamRuntime 入口创建 trace，下游 SkillRunner/Tool 自动嵌套。

#### 4.12.3 插桩点：全部落在既有收口处，业务代码零侵入

| 插桩点 | 捕获内容 | 说明 |
|---|---|---|
| `LLMService`（全系统唯一 LLM 出口） | prompt/completion/usage/延迟/TTFT/流式分片 | **收益最大的一处**：自研 provider 已收口，接一次 = 所有 Agent 的所有调用全覆盖（Langfuse OpenAI 包装或 `@observe` 装饰器，仅改 provider 基类） |
| `SkillRunner.run / run_with_react` | skill 执行 span + ReAct 反思轮次 | 基类统一装饰 |
| `Tool` 基类 `execute` | 工具调用 span + 权限决策结果 | 与 §4.11.2 权限校验同点埋入，天然对齐 |
| `TeamRuntime` 主循环 | trace 创建 + 轮次/熔断/HITL 事件 | 入口一处 |
| FastAPI 入口 + BackgroundTasks | 异常/性能/用户上下文 | Sentry ASGI middleware + asyncio 异常钩子；后台任务在 finally 兜底块主动 capture（后台异常不冒泡到请求） |
| SQLAlchemy | 慢查询 | Sentry performance 集成 |

采样策略：LLM generation 全量（调用本身昂贵，观测开销可忽略）；tool span 按 org 可配采样；失败任务强制留全轨迹。

#### 4.12.4 多租户与数据边界

- **Langfuse 必须自托管**（Docker Compose，数据不出内网）——prompt 中必然含客户资料，SaaS 版直接违反数据边界原则。按环境分 project（prod/staging），**不按租户分**：Langfuse UI 只给研发/运营用，不暴露给租户，租户隔离仍由我方 API 层负责。
- 敏感字段经 Langfuse masking 钩子脱敏（手机号/邮箱正则 + agents_md 机密段标记）后入库。
- **Sentry 不收 prompt 内容**（那是 Langfuse 的职责）——只收堆栈与结构化 tag：`org_id/team_id/task_id/run_id/agent_id/model`，一个异常直接定位到「哪个组织的哪个团队的哪个员工哪一步」；PII 清洗开 server-side scrubbing。

#### 4.12.5 闭环：评估与告警

- **评估闭环**（接 Phase 3 评估 harness）：Langfuse datasets 定期导出 supervisor 路由轨迹（dispatch 决策 + 结果成败）为数据集；agents_md / 角色模板 / SOP 改版后跑回归评分——对应风险表「supervisor 路由质量」的 CI 化。
- **告警双通道不混**：研发 oncall 走 Sentry（错误率、延迟、后台任务失败）；业务风控告警（预算/熔断/kill switch）走产品内 HITL 通知通道（§4.11.4），用户可见。
- **业务大盘不依赖 Langfuse**：token/成本看板从 `usage_ledger` 聚合表出（Grafana/Metabase 直连），Langfuse 停服不影响用户查账。

### 4.13 对话式入口与 @ 直接执行

团队对话线程（`conversations.scope_type='team'`，复用现有 thread 体系）是任务下发的主入口之一，两种寻址模式并存：

| 模式 | 触发 | 执行路径 |
|---|---|---|
| supervisor 路由（默认） | 消息不含 @，或 @supervisor | 意图 `team_dispatch` → 创建 team_task → supervisor 循环（§4.2） |
| **@ 直接执行（direct）** | 消息 @某员工 | 确定性解析（正则 + roster 匹配，先于 LLM 意图分类的 fast-path）→ 创建 `mode=direct` 的 team_task → 该员工单次执行，**无 supervisor 规划轮** |

设计要点：

- **direct 任务机制一项不少，只跳过规划**：信箱照走（supervisor 抄送可见，保持团队感知）、task_runs/checkpoint 照记、预算照扣（团队默认预算）、权限校验/L2 工具 HITL 照常、episodic 记忆照写——直达不等于脱管。
- **多轮上下文衔接**：direct 模式下 ContextGovernor 装配增加「线程近 K 轮对话」段，员工的回答自然衔接对话前文；supervisor 模式的上下文仍来自任务包。
- **约束（MVP）**：单条消息只解析第一个 @；@多个员工回退默认路由（supervisor 分派）；@不存在/fired 员工 → 澄清卡片；目标员工忙碌（per-agent 锁被占）→ 入等待队列并在 roster 显示忙碌状态。
- **员工间 @**（Phase 3）：员工 report/consult 中 @同事即 p2p 协作入口，与 consult/handoff 机制合流。

---

## 5. 实施路线图

| 阶段 | 周期 | 交付 | 验收标准 |
|---|---|---|---|
| **Phase 0 地基** | ~2 周 | organizations/org_members/quotas + 双列 ownership + Tool 层 ACL（存量用户自动迁移为个人组织）；工具敏感度分级（L0/L1/L2）+ `audit_logs` 只增表；SkillExecution 泛化为 run 记录（加 task 关联）；Postgres 为默认部署 | 两个组织各自建 KB，互相检索不到对方数据；同组织内 admin 与 member 的 hire/fire 权限差异生效；未授权工具调用被拒并落审计 |
| **Phase 1 团队 MVP** | 4-6 周 | agents/teams + hire/fire API 与管理页（含模板克隆 hire）；Supervisor 循环 + 信箱 + 预算熔断 + 基础 HITL；`usage_ledger` 计量 + 四级预算硬停 + L2 工具强制 HITL；Langfuse/Sentry 接入（LLMService/SkillRunner/Tool 基类/TeamRuntime 四个插桩点，随内核一起改一次到位）；任务流 SSE（agent_message chunk）；员工 = 现有 6 个 Skill 的授权组合 | 用户建 3 人团队（策划/视觉/导出），下任务「给 X 公司出方案」，supervisor 正确 @ 三人并产出带溯源的 Artifact；超预算自动 HITL；账单可按团队/角色查看；Langfuse 中可见完整任务 trace 树，Sentry 告警带 task_id 定位 |
| **Phase 2 记忆+定时** | 3-4 周 | 三层记忆 + 蒸馏 job + 共享块；ContextGovernor 统一两套 ContextPack；schedules + APScheduler；风控规则引擎（限速/异常消耗熔断/失败熔断/kill switch）+ 成本报表定时任务 | 跨任务问「上次那个客户的结论」员工能答（episodic→semantic）；cron 任务每日自动生成日报 Artifact；人为构造异常消耗能触发自动挂起与通知 |
| **Phase 3 深化** | 持续 | 员工 p2p consult/handoff（受 max_depth=2 灰度）、Agent 模板市场（一键 hire 预置角色）、A2A 协议对外互联、评估 harness（基于 Langfuse datasets 的 supervisor 路由质量回归，§4.12.5）、副作用工具子进程池 → 外部租户容器沙盒（L2/L3） | 外部 A2A Agent 可被 hire 为远程成员并参与任务 |

### 现有系统的迁移策略

- canvas 六阶段流水线**不重写**：Phase 1 中将其包装为「内置策划团队」的一个 supervisor SOP（pipeline_stages manifest 直接映射为 dispatch 顺序），新旧路径共存；意图路由的硬编码白名单随 roster 动态生成，消除「新增角色改 5 处代码」问题。

---

## 6. 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| Token 成本爆炸（多 Agent 天然放大） | 高 | 四级预算强制（§4.11.4）；supervisor 路由用轻模型（model_alias 按 seat_role 默认分级）；信箱消息默认摘要化 |
| Supervisor 路由质量差 → 任务空转 | 高 | roster 能力自述卡（hire 时生成）；乒乓检测；评估 harness 纳入 CI |
| SQLite 单写者 vs 并行员工 | 中 | 生产强制 Postgres；沿用「每长耗时操作独立 session」既有模式；per-agent 锁串行化 |
| agents.md 提示注入 | 中 | 工具白名单 + untrusted 段标记 + 指令层级 + L2 工具强制 HITL + 沙盒分级（§4.11.2/4.11.3） |
| 自研内核工作量失控 | 中 | 内核收敛为四件套（循环/checkpoint/信箱/记忆块），其余全部复用；TeamRuntime.execute 抽象保底可换 LangGraph |
| 记忆蒸馏质量差污染共享块 | 中 | 共享块写权限收口 supervisor；蒸馏产出附来源 run_id 可回溯可删除 |
| 审计/计量数据膨胀 | 低 | audit_logs 按时间分区 + 热数据保留策略；usage_ledger 聚合表预结算，流水可归档 |

---

## 7. 参考资料

- 框架横评：[Towards AI Production Guide 2026](https://pub.towardsai.net/langgraph-vs-crewai-vs-autogen-which-ai-agent-framework-should-your-enterprise-use-in-2026-3a9ebb407b09)、[Splunk Top Agent Frameworks 2026](https://www.splunk.com/en_us/blog/learn/agent-frameworks.html)、[JetBrains Framework Comparison](https://www.jetbrains.com/pages/ai-agents/building/agent-framework-comparison)
- AutoGen → Microsoft Agent Framework：[官方 Overview](https://learn.microsoft.com/en-us/agent-framework/overview)、[迁移指南](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen)、[v1.0 GA 公告](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0)
- LangGraph HITL/许可：[Interrupts 文档](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Persistence 文档](https://docs.langchain.com/oss/python/langgraph/persistence)、[HITL 博客](https://www.blog.langchain.com/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt/)
- MetaGPT：[GitHub](https://github.com/foundationagents/metagpt)、[MultiAgent 101 文档](https://docs.deepwisdom.ai/main/en/guide/tutorials/multi_agent_101.html)、[MGX 发布](https://github.com/foundationagents/metagpt)
- A2A 协议：[Google 发布博客](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability)、[a2aproject/A2A](https://github.com/a2aproject/A2A)、[2026 采用现状评估](https://www.glukhov.org/ai-systems/comparisons/a2a-protocol-2026-adoption)
- 记忆架构：[Letta Memory Blocks](https://www.letta.com/blog/memory-blocks)、[Mem0 vs Letta 对比](https://vectorize.io/articles/mem0-vs-letta)、[Mastra Agent Memory](https://mastra.ai/articles/agent-memory)
- 竞品：[Coze 3.0 多人多Agent 模式报道](https://finance.sina.com.cn/wm/2026-06-03/doc-inhzzyte2869078.shtml)、[扣子多 Agent 文档](https://docs.coze.cn/guides_multiagent)、[Dify 官网](https://dify.ai/zh)
