# Canvas 左侧对话主链路稳定性 Spec

## 背景

Canvas 左侧对话当前有三类使用方式：

1. 项目全局对话
2. 节点级对话（node-scoped conversation）
3. 历史版本浏览时的只读查看

现状中这三者共享同一个 project conversation，但历史加载没有按 scope 过滤，切节点、退出节点对话、切历史版本后，旧节点消息会继续出现在当前视图里，形成串话和错误上下文。

## 目标

稳住 canvas 左侧对话这条主链路，保证：

1. 节点级对话只显示该节点自己的往返消息
2. 返回项目全局对话后，不再显示任何节点级消息
3. 切换到另一个节点后，上一节点消息不再残留
4. 切换历史版本或只读版本后，节点级上下文立即退出，不带入旧节点消息
5. 切 scope 过程中，如果旧请求仍在流式返回，不得污染新 scope 的消息区

## 非目标

1. 不改 Conversation 数据模型，不拆成多条 conversation
2. 不做多版本独立聊天树
3. 不修改节点建议本身的生成策略
4. 不改导出、视觉版本树、右侧节点编辑抽屉

## 术语

- `global scope`：`activeNodeId = null`，项目级对话
- `node scope`：`activeNodeId = <node_id>`，单节点对话
- `legacy node turn`：历史数据里 user message 未写入 `metadata.node_id`，但 assistant message 已带 `metadata.node_id`

## 期望行为

### 1. 历史加载

`GET /api/v1/projects/{project_id}/conversation`

- 不带 `node_id` 时，只返回 global scope 历史
- 带 `node_id` 时，只返回该节点 scope 历史
- 返回的 `conversation.id` 保持 project conversation 不变

### 2. 消息归属规则

一轮 node-scoped turn 中：

- user message 持久化时写入 `metadata.node_id`
- assistant message 持久化时继续写入 `metadata.node_id`

兼容历史数据：

- 若 user message 没有 `metadata.node_id`
- 但它后面直到下一条 user message 之前，存在 assistant message，且其 `metadata.intent == "node_edit"` 且 `metadata.node_id == X`
- 则该 user message 视为属于节点 `X`

### 3. 前端 scope 切换

当 `activeNodeId` 或 projectId 变化时：

1. 中断当前 SSE 流
2. 清空 streaming 临时状态
3. 重新按 scope 拉取历史
4. 仅接受当前 scope 对应请求的回调结果

### 4. 历史版本边界

- 进入只读历史版本后，必须退出 node scope
- 退出 node scope 后，左侧面板显示 global scope 历史，不显示刚才节点的消息
- 只读版本下如果再次点节点，不应保留节点级聊天上下文

## 验收标准

1. 节点 A 发送一轮，再切到节点 B，B 视图中看不到 A 的 user / assistant 消息
2. 从节点 A 退回项目全局，消息区只剩 global scope 消息
3. 历史里存在 legacy node turn 时，global scope 也不会把该 user turn 漏出来
4. 流式回复中切节点，旧流后续 chunk 不会写进新节点视图
5. 切到历史版本后，节点标签消失，消息区不残留旧节点消息

## 实现约束

1. 遵循现有 project conversation 单线程模型
2. 优先增量修复，不引入新的状态容器
3. 用 TDD 先补回归，再改实现
