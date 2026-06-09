# Feishu Session Sync — 双向远程指挥插件设计

> 日期：2026-06-09
> 状态：已批准

## 1. 目标

让用户在离开电脑时，通过飞书群实时查看 Claude Code 的工作状态，并远程发送指令指挥下一步工作。

## 2. 方案选型

**选定方案：Hooks + lark-cli + 文件队列**

- 出站：Claude Code hooks → shell 脚本 → lark-cli 发飞书消息
- 入站：飞书群回复 → poll-commands.sh 轮询 → commands.jsonl → CronCreate 定时消费
- 优点：仅依赖 lark-cli（已配置）+ Claude Code 原生 hooks/cron，无需额外服务器
- 缺点：指令有几分钟延迟（轮询间隔），对远程指挥场景可接受

## 3. 文件结构

```
.claude/
  feishu-sync/
    ├── bin/
    │   ├── send-notification.sh    # Hook 调用 → 发飞书消息
    │   ├── poll-commands.sh        # 定时轮询飞书新消息 → 写入队列
    │   └── format-message.sh       # 消息格式化工具
    ├── queue/
    │   ├── commands.jsonl          # 待处理指令（一行一条 JSON）
    │   └── processed.jsonl         # 已处理指令（归档）
    ├── state/
    │   └── session_state.json      # 当前会话状态
    └── config.json                 # 配置：飞书群 ID、轮询间隔等
```

## 4. 出站通知（Claude → 飞书）

### 4.1 Hook 事件

| 事件 | Hook 类型 | 触发时机 |
|------|----------|---------|
| 任务通知 | `Notification` | Claude 通知用户时 |
| 会话停止 | `Stop` | Claude 停止时（正常/异常） |

### 4.2 消息格式（飞书 Markdown）

通知消息：

```
🚀 开始工作

📋 任务：{任务描述}
📁 项目：{项目名}
⏰ 时间：{时间戳}

---
💡 回复指令：继续 | 进度 | 停下来 | 或输入具体需求
```

完成消息：

```
✅ 任务完成

📋 任务：{任务描述}
⏱️ 耗时：{duration}
📝 结果摘要：{摘要}

---
💡 回复指令：继续 | 进度 | 或输入新的需求
```

等待确认消息：

```
⏸️ 等待确认

❓ {确认问题}
⚡ 需要你回复来继续

---
回复 "确认" 或 "取消"，或输入修改意见
```

错误消息：

```
❌ 任务中断

📋 任务：{任务描述}
⚠️ 错误：{错误信息}

---
回复指令：重试 | 换个方式 | 查看日志
```

### 4.3 Hooks 配置

写入 `.claude/settings.json`：

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/feishu-sync/bin/send-notification.sh notification \"$CLAUDE_NOTIFICATION\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/feishu-sync/bin/send-notification.sh stop"
          }
        ]
      }
    ]
  }
}
```

## 5. 入站指令（飞书 → Claude）

### 5.1 指令类型

| 类型 | 示例 | 解析方式 |
|------|------|---------|
| short_command | "继续"、"停"、"重新来"、"换个方案" | 精确关键词匹配 |
| flow_control | "先做 Task 3"、"跳过测试"、"查看进度" | 关键词 + 参数提取 |
| requirement | "把视觉风格改成科技感"、"第三章节重写" | 原文透传给 Claude |
| status_query | "进度？"、"现在在干嘛？" | 关键词匹配 → 返回 session_state |

### 5.2 关键词映射

```
继续/continue/go/go on     → continue
停/暂停/stop/wait/pause     → pause
重新来/重来/redo/restart    → restart
换个方案/换方案/try another → try_alternative
进度/状态/status/progress   → status_query
确认/ok/yes/好的            → confirm
取消/no/不要/cancel         → cancel
```

其他所有输入 → 默认按 requirement 类型透传。

### 5.3 commands.jsonl 格式

```jsonl
{"id":"cmd_001","ts":"2026-06-09T15:40:00Z","type":"short_command","raw":"继续","parsed":"continue","status":"pending"}
{"id":"cmd_002","ts":"2026-06-09T15:42:00Z","type":"flow_control","raw":"跳过测试直接提交","parsed":{"action":"skip","target":"test","then":"commit"},"status":"pending"}
{"id":"cmd_003","ts":"2026-06-09T15:45:00Z","type":"requirement","raw":"把视觉风格改成科技感","status":"pending"}
```

### 5.4 指令消费流程

CronCreate 每 3 分钟触发：

1. 读取 `commands.jsonl` 中 status=pending 的记录
2. 按 type 分发：
   - short_command → 执行预定义动作
   - flow_control → 调整任务优先级
   - requirement → 作为新 prompt 直接执行
   - status_query → 读取 session_state 并通过飞书回复
3. 标记 status=completed，追加到 processed.jsonl
4. 通过 send-notification.sh 回复处理结果

## 6. 会话状态

### 6.1 session_state.json 结构

```json
{
  "session_id": "",
  "project": "",
  "current_task": "",
  "status": "idle|working|waiting|error",
  "started_at": "",
  "last_update": "",
  "todos": [
    {"content": "", "status": "pending|in_progress|completed"}
  ],
  "last_output_summary": "",
  "last_feishu_msg_id": "",
  "last_polled_msg_id": ""
}
```

### 6.2 状态更新

- send-notification.sh 每次发送通知时更新 status 和 last_update
- CronCreate 消费指令时更新 current_task 和 todos

## 7. 安全

- 只处理来自配置用户 ID 的飞书消息（config.json 中 `allowed_user_ids`）
- 指令长度限制 500 字符
- 不执行任意 shell 命令，只做预定义动作 + 需求透传
- session_state.json 只存摘要，不暴露完整对话或敏感信息

## 8. 配置

### config.json

```json
{
  "feishu_chat_id": "oc_xxxxx",
  "feishu_bot_name": "Claude Code 助手",
  "poll_interval_seconds": 180,
  "max_command_length": 500,
  "allowed_user_ids": ["ou_xxxxx"],
  "notification_events": ["task_start", "task_complete", "error", "waiting_confirmation"]
}
```

### 首次设置步骤

1. 确认 lark-cli 已配置并可正常发消息
2. 创建飞书群（或用现有的），拉 Bot 进群
3. 获取 chat_id 写入 config.json
4. 获取你的 user_id 写入 allowed_user_ids
5. 测试 send-notification.sh 手动发送一条消息
6. 测试 poll-commands.sh 能否读取飞书消息
7. 配置 hooks 到 settings.json
8. 启动 CronCreate 定时任务

## 9. 依赖

- `lark-cli` — 飞书命令行工具（已安装在 `/Users/tutu/.lark-cli/`）
- Claude Code hooks — 事件触发
- Claude Code CronCreate — 定时轮询指令队列

## 10. 后续扩展

- 微信企业号 webhook 支持（作为备用通道）
- 飞书互动卡片（更丰富的 UI）
- OpenClaw WebSocket 实时桥接（减少延迟）
- 多项目独立通知群
- 工作日报自动推送
