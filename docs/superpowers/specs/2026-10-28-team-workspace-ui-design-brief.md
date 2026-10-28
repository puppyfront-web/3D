# 团队工作台与任务视图 — Phase 1 前端设计 Brief

> 日期：2026-10-28
> 依据：[2026-10-24-ai-team-platform-system-design.md](./2026-10-24-ai-team-platform-system-design.md) §1.5（API/SSE）、§3.3（前端页面）、§3.4（验收）
> 状态：**待确认** — 本文档是 shape 产物（规划，不含实现）。确认后可交 `$impeccable craft` 或直接实现。
> 视觉方向探针：已跳过（当前环境无原生图像生成能力）。

---

## 1. Feature Summary

为 AI 团队平台 Phase 1（团队 MVP）交付四类前端页面：**团队工作台**（roster 管理）、**团队对话视图**（线程 + @直达）、**任务视图**（信箱时间线 + HITL 审批）、**组织管理**（成员/配额/审计/账单）。用户是组织成员（owner/admin/member）：他们组建 AI 团队、用自然语言下任务、看 AI 员工协作过程、在关键节点做人工决策。这是把营销页已经讲出的「AI 团队」故事第一次变成可用的产品事实，同时消灭「营销卖团队、工作台给项目列表」的词汇断层（critique P1-1）。

## 2. Primary User Action

**下一条任务，并在它执行时看懂发生了什么。** 一切布局服务于这个动作：输入框永远可输入、时间线永远在更新、需要你决策的卡片永远显眼（HITL 到达时它必须是屏幕上最亮的东西）。

## 3. Design Direction

- **色彩策略**：Restrained（产品默认）。薰衣草蓝 #5E6AD2 只用于「进行中/品牌身份/主操作」；语义色沿刚统一的 StatusBadge 词汇：brand=进行中、info=审核中/等待人工、warning=预算预警、success=完成、neutral=排队/已停用、error=失败。
- **场景句**：内部成员在办公桌前（桌面优先，Chrome/Edge，双显示器常见），白天长时间开着这个页面处理真实客户任务——需要安静、可长时间注视的亮色界面，深色只属于营销页。
- **锚点参考**：
  - **Linear**——roster 侧栏的密度、hairline 分隔、键盘优先、`Cmd+K`；
  - **Slack 线程**——信箱时间线的「@提及高亮 + 消息归属头像 + 左侧无限滚动」语汇（用户已有肌肉记忆）；
  - **Stripe Dashboard**——用量账单的「汇总卡 + 按团队/角色下钻 + 月份切换」结构。

## 4. Scope

- **保真度**：production-ready（Phase 1 验收即 UAT 对象）。
- **广度**：spec §3.3 四类页面 + TopNav/admin 侧栏 IA 调整（承载新页面的最小改动）。
- **交互**：真实可用组件（SSE 流式渲染、审批操作、hire/fire 表单），非原型。
- **不含**：Phase 2 的记忆/定时/风控页面、A2A、模板市场（spec Phase 3）。

## 5. Layout Strategy

### 5.0 IA 变更（承载层，最小改动）

- TopNav（workspace 变体）：新增 **「团队」**（`/workspace/teams`，默认团队工作台）；「团队工作台」改名「项目」过渡保留（见 §10 默认决策 D1）。
- **全局任务感知位**（critique 结构性风险）：TopNav 右侧加一个「进行中任务」徽章（数字 + 呼吸点），点击进入任务视图；`waiting_human` 到达时徽章变为 info 色并置顶该任务。这是 budget_warning/hitl_request 的全局落点。
- admin 侧栏：17 项按 spec §1.6 三分重组——**平台知识资产**（案例/话术/SOP/模板/规则/风格）、**租户资产**（知识库/评测）、**平台运营**（设置/审计/账单——后两项 link 到组织管理页）。SKU 门控项在各分组头部标注「完整版」。

### 5.1 团队工作台 `/workspace/teams/[id]`

三段式：**roster 卡片区**（网格，2-3-4 列响应式）→ **团队信息条**（名称/描述/SOP 绑定/预算余量水位条）→ **最近任务列表**。
roster 卡片：头像 + 名字 + 职位 + 状态徽章（在线=brand 呼吸点 / 忙碌=warning / fired=neutral 灰显整卡）+ 能力 chips（tool/skill grants 摘要）+ 悬停操作（查看/编辑）。**员工编辑器**：与 hire 第二步同一表单（Drawer 复用）——persona 文本域 / agents_md 代码域（等宽字体）/ grants 复选组 / model 别名 Select / max_context_tokens；保存前 diff 提示（grants 变更即时生效于下次 dispatch）。**hire 向导**：右侧滑入 Drawer（非 modal——不遮挡 roster 对比），三步：选模板/从空白 → 配 persona+grants（复选组，按 skill 分组）→ 确认卡（展示将消耗的配额）。**fire 确认**：Dialog，必填 reason（textarea），红字说明「信箱历史保留，员工从花名册移除」。

### 5.2 团队对话视图 `/workspace/chat`（团队线程）

现有 ConversationPanel 的左侧扩展：**roster 侧栏**（w-60，可折叠；成员卡：头像/名/在线·忙碌点/职责一行；fired 折叠到「已离开」分组）。输入框支持 **@ 自动补全**（输入 `@` 弹出成员浮层：键盘上下选择，Enter 确认；展示成员状态——忙碌者标注「将排队」）。无 @ 时输入即走 supervisor 路由，发送后助手回复以 **info 徽章「已转 AI 大脑调度」** 开头；@某人时该员工头像标记本条消息，流式回复期间徽章为 brand「直达执行」。**复用**现有气泡流、思考面板、附件托盘、content-block 渲染器——对话视图不是新面板，是现有面板的团队化扩展（spec §1.7 集成点）。

### 5.3 任务视图 `/workspace/tasks/[id]`

单列时间线（max-w-3xl 居中，与对话视图同构）：
- **顶部状态条**（sticky）：任务标题 + 状态徽章 + **轮次进度**（第 N 轮·max_rounds）+ **预算水位条**（0-80% primary、≥80% warning、100% error + 硬停提示）。
- **runs 状态条**（状态条下方，单行横排）：每个 task_run 一枚 chip——`员工名 · run 角色 · 状态点`（running=brand 呼吸 / completed=success / failed=error / interrupted=info），点击 chip 滚动定位到该 run 的信箱区段；心跳超时恢复的 run 显示「已从 checkpoint 恢复」。
- **信箱时间线**：agent_message 逐条渲染——from 头像 + 名字 + → to + 文本（@提及 lavender 高亮）；DISPATCH 消息折叠为「派发给 策划专家 ▸」单行可展开；REPORT 消息带产物引用卡（复用 Artifact 组件 + used_cases/used_chunks 溯源列表）。
- **HITL 审批卡**：时间线内嵌，info 色左边框性容器 + 问题描述 + 选项按钮组（primary 主选项 + outline 其余 + 「备注」折叠输入）；提交后卡片转为「已批准：选项 B · 备注」灰态记录。**中断感设计**：不做 modal（见 §10 D2）——卡片 + 全局徽章 + toast 三层，但时间线自动滚动到卡片并 400ms 脉冲一次。
- **崩溃恢复态**：任务从 checkpoint 重放时，时间线顶部插入 neutral 卡「进程重启，已从第 N 轮恢复」。

### 5.4 组织管理 `/workspace/org`

四个 Tab（成员与角色 / 配额 / 审计 / 用量账单），沿用 admin 表格语汇（这是 owner/admin 的低频后台面，密度优先）：
- 成员表：邮箱/角色（owner·admin·member 徽章）/状态/加入时间/操作。
- 用量账单：Stripe 式——顶部 3 张汇总卡（本月 token/成本/按团队 top3），下钻表格（团队 × 角色 × 月），数据源 `GET /orgs/{id}/usage`。
- 审计查询：过滤器（action/agent/时间范围）+ 分页表，行点击展开 context_json。

## 6. Key States

| 状态 | 团队工作台 | 对话视图 | 任务视图 | 组织管理 |
|---|---|---|---|---|
| 空态 | 「还没有员工」引导卡 → hire 向导第一步 | 系统欢迎消息（AI 大脑自介绍 + 示例任务 3 条可点击） | 不适用（从别处进入） | 「邀请第一位成员」 |
| 加载 | roster 骨架屏（卡片形，替换 spinner——critique 发现） | 现有骨架 | 时间线骨架（3 条灰条） | 表格骨架行 |
| 流式中 | — | @直达回复流式 + 思考面板 | agent_message 实时追加 + 打字机光标 | — |
| **等待人工** | — | 输入框上方浮出「任务等待你的决策 →」条 | **HITL 审批卡**（§5.3）+ 全局徽章 | — |
| **预算预警** | 团队信息条水位 ≥80% warning | — | 水位条 warning + `budget_warning` toast | 账单页顶部警示条 |
| 预算硬停 | — | — | 状态条 error「预算已耗尽，等待人工决策」+ HITL 卡 | — |
| @不存在的员工 | — | **澄清卡片**（info）：「没有找到 @xxx，是想要：成员A/成员B/重新描述？」 | — | — |
| @fired 员工 | — | 澄清卡片 + 「已离开」侧栏分组引导 | — | — |
| 目标忙碌 | roster 卡片 warning 点 | 补全浮层标注「将排队」；发送后 toast「已排队，前方还有 N 个任务」 | DISPATCH 前显示排队徽章 | — |
| @多个员工 | — | 回退提示卡（info）：「检测到 @A @B，已转 AI 大脑统一调度」 | mode=supervisor 正常流程 | — |
| SSE 断线 | — | 顶部黄条「连接中断，重连中…」+ 自动重连指数退避；恢复后补放 missed 消息 | 同左 + 时间线「已恢复，补齐 N 条」 | — |
| 错误 | hire 失败行内错误 | 发送失败重试气泡 | REPORT 错误条（error）+ 任务级重试按钮 | 表格错误态 + 重载 |

（前三项边界场景直接对应 spec §3.4 验收 5。）

## 7. Interaction Model — SSE chunk → UI 映射

| SSE type（spec §1.5） | UI 落点 | 细节 |
|---|---|---|
| `agent_message` | 时间线条目 / 对话气泡 | `{from,to,msg_type,seq}`；seq 保证重连去重排序；msg_type=DISPATCH 折叠、REPORT 带产物卡 |
| `task_status` | 任务状态条 + TopNav 徽章 | `{status,round,budget_pct}`；round 驱动「第 N 轮」，budget_pct 驱动水位条 |
| `hitl_request` | HITL 审批卡 + 全局徽章 + toast | `{review_id,question,options}`；POST `/tasks/{id}/reviews/{rid}` 后卡片转灰态 |
| `roster_change` | roster 侧栏/卡片徽章 + 时间线系统消息 | hire→brand 徽章「已加入」；fire→neutral「已离开（reason）」 |
| `budget_warning` | 水位条变色 + toast（80 首次一次） | level=100 时叠加状态条 error 与硬停 HITL 卡 |

**操作流**：新建任务（对话输入框或工作台「下任务」按钮）→ 流式时间线 →（等待人工：审批卡提交 → 续流）→ finalize → 产物卡 + 「查看溯源」抽屉 → 完成。取消：任务视图右上「取消任务」→ 确认 Dialog（说明已消耗预算不退还）→ `POST /tasks/{id}/cancel`。

## 8. Content Requirements

- **新词表**（对齐 spec，替代「项目」语境）：团队 / 员工 / 花名册 / 任务 / 信箱 / 派发 / 汇报 / 审批 / 预算水位 / 轮次。文案全中文，避免「mailbox/budget」英文直出。
- **微文案**：空态见 §6；hire 第三步「将占用 1/8 员工配额」；水位 80%「预算接近上限（剩余 20%），任务将在耗尽时暂停等待决策」；硬停「预算已耗尽。可选择：追加预算 / 终止任务」。
- **缺失信息纪律**（AGENTS.md）：产物卡继承 ⚠️「需要进一步确认」清单组件（已存在于 Artifact 渲染）。
- 动态范围：roster 1-8 员工（quota 上限）；任务轮次典型 3-8、上限 max_rounds；信箱消息典型 10-40 条/任务；账单行数 ≤ 团队数×4。

## 9. Recommended References（实现时）

`layout.md`（时间线/侧栏结构）、`animate.md`（SSE 逐条追加与水位条动效，全部 ≤250ms + reduced-motion）、`harden.md`（断线重放、seq 去重、边界态）、`document.md` 产出的 DESIGN.md（token 纪律）。

## 10. 默认决策（已断言，可推翻）

- **D1 词汇断层（P1-1）**：Phase 1 上线即以「团队/任务」为首层名词；现有「项目列表」保留为「项目」入口（知识问答容器，spec §1.7 team thread 是轻量入口，两者并存）；hero CTA「立即派发任务」改落 `/workspace/chat`（团队线程）而非项目向导。**不**做「项目=任务的工作区」过渡文案——直接切换，旧项目数据不动。
- **D2 HITL 中断感**：inline 卡片 + 全局徽章 + 单次脉冲，**不做 modal**（用户可能正在输入长任务描述，modal 会丢焦点毁输入）。
- **D3 预算水位呈现**：owner/admin 与 member 同视图（MVP 不分角色裁剪；spec 未要求，避免双倍维护）。
- **D4 hire 向导用 Drawer 不用全屏**：保留 roster 上下文。
- **D5 admin 重组只动导航分组，不迁移页面路由**：URL 稳定，风险最小。

## 11. Open Questions

无——以上均有断言默认值。确认时请点名要推翻的编号即可。
