# Feishu Session Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bidirectional Feishu notification plugin that pushes Claude Code session status to a Feishu group and accepts remote commands back.

**Architecture:** Claude Code hooks fire shell scripts that call `lark-cli` to send notifications outbound. A `poll-commands.sh` script reads new Feishu messages and writes them to a JSONL queue. Claude Code's CronCreate periodically consumes the queue and executes commands, replying results back to Feishu.

**Tech Stack:** Shell scripting, `lark-cli` (npm CLI for Feishu API), Claude Code hooks + CronCreate, JSON/JSONL for data.

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Create | `.claude/feishu-sync/config.json` | Feishu chat ID, user allowlist, poll interval |
| Create | `.claude/feishu-sync/bin/send-notification.sh` | Called by hooks — formats + sends Feishu message |
| Create | `.claude/feishu-sync/bin/poll-commands.sh` | Reads Feishu messages, writes to command queue |
| Create | `.claude/feishu-sync/bin/format-message.sh` | Shared message formatting utility |
| Create | `.claude/feishu-sync/bin/setup.sh` | First-time setup: create group, get IDs |
| Create | `.claude/feishu-sync/state/session_state.json` | Current session state (task, progress, status) |
| Create | `.claude/feishu-sync/queue/commands.jsonl` | Pending commands from Feishu (empty initially) |
| Create | `.claude/feishu-sync/queue/processed.jsonl` | Processed commands archive (empty initially) |
| Modify | `.claude/settings.local.json` | Add hooks configuration (Notification, Stop) |

---

## Task 1: First-Time Setup Script

**Files:**
- Create: `.claude/feishu-sync/bin/setup.sh`

This script creates the Feishu group, gets the chat_id, and writes config.json. Run once manually before everything else.

- [ ] **Step 1: Create setup.sh**

```bash
#!/usr/bin/env bash
# .claude/feishu-sync/bin/setup.sh
# First-time setup: creates Feishu group, saves config
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SYNC_DIR/config.json"
STATE_DIR="$SYNC_DIR/state"
QUEUE_DIR="$SYNC_DIR/queue"

# Create directories
mkdir -p "$STATE_DIR" "$QUEUE_DIR"

# Initialize empty queue files
: > "$QUEUE_DIR/commands.jsonl"
: > "$QUEUE_DIR/processed.jsonl"

# Check lark-cli is available
if ! command -v lark-cli &>/dev/null; then
  echo "❌ lark-cli not found. Install with: npm install -g @larksuite/cli"
  exit 1
fi

echo "✅ lark-cli found at $(which lark-cli)"

# Prompt for chat ID (user can create group manually or provide existing one)
echo ""
echo "请提供飞书群 chat_id (oc_ 开头)。"
echo "如果还没有群，可以先创建一个，把 Bot 拉进去，然后提供 chat_id。"
echo "你可以用以下命令搜索已有群："
echo "  lark-cli im +chat-search --query \"群名\" --format json"
echo ""
read -rp "飞书群 chat_id: " CHAT_ID

if [[ -z "$CHAT_ID" ]]; then
  echo "❌ chat_id 不能为空"
  exit 1
fi

# Verify the chat exists
echo "验证群聊..."
if ! lark-cli im chats get --chat-id "$CHAT_ID" --format json &>/dev/null; then
  echo "⚠️  无法访问群 $CHAT_ID，请确认 Bot 已加入该群"
  exit 1
fi

echo "✅ 群聊验证成功"

# Default user ID from lark-cli config
DEFAULT_USER_ID="ou_fca36e6ea3cecdc9660b1d2ae6e4544c"

# Write config
cat > "$CONFIG_FILE" <<EOF
{
  "feishu_chat_id": "$CHAT_ID",
  "feishu_bot_name": "Claude Code 助手",
  "poll_interval_seconds": 180,
  "max_command_length": 500,
  "allowed_user_ids": ["$DEFAULT_USER_ID"],
  "notification_events": ["task_start", "task_complete", "error", "waiting_confirmation"]
}
EOF

# Initialize session state
cat > "$STATE_DIR/session_state.json" <<'EOF'
{
  "session_id": "",
  "project": "",
  "current_task": "",
  "status": "idle",
  "started_at": "",
  "last_update": "",
  "todos": [],
  "last_output_summary": "",
  "last_feishu_msg_id": "",
  "last_polled_msg_ts": "0"
}
EOF

echo ""
echo "✅ 配置完成！"
echo "   config.json: $CONFIG_FILE"
echo "   session_state.json: $STATE_DIR/session_state.json"
echo ""
echo "发送测试消息..."
TEST_MSG=$'🤖 Claude Code 飞书同步插件已连接\n\n后续你可以在这里查看工作状态并发送远程指令。'
lark-cli im +messages-send --chat-id "$CHAT_ID" --text "$TEST_MSG" --as bot

echo ""
echo "✅ 测试消息已发送！请检查飞书群。"
echo ""
echo "下一步：配置 Claude Code hooks（见 Task 5）"
```

- [ ] **Step 2: Make executable and test setup script help**

Run:
```bash
chmod +x .claude/feishu-sync/bin/setup.sh
ls -la .claude/feishu-sync/bin/setup.sh
```
Expected: `-rwxr-xr-x` permissions shown

- [ ] **Step 3: Run setup interactively**

Run:
```bash
.claude/feishu-sync/bin/setup.sh
```
Expected: Prompts for chat_id, verifies, writes config.json and session_state.json, sends test message to Feishu

- [ ] **Step 4: Verify config files created**

Run:
```bash
cat .claude/feishu-sync/config.json
cat .claude/feishu-sync/state/session_state.json
```
Expected: Valid JSON with chat_id and user IDs filled in

- [ ] **Step 5: Commit**

```bash
git add .claude/feishu-sync/bin/setup.sh
git commit -m "feat(feishu-sync): add first-time setup script"
```

---

## Task 2: Message Formatting Utility

**Files:**
- Create: `.claude/feishu-sync/bin/format-message.sh`

This is a shared utility sourced by other scripts. It provides functions to format different notification types into Feishu-compatible text.

- [ ] **Step 1: Create format-message.sh**

```bash
#!/usr/bin/env bash
# .claude/feishu-sync/bin/format-message.sh
# Shared message formatting functions. Sourced by other scripts.
# Usage: source "$(dirname "$0")/format-message.sh"

SYNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Read a field from session_state.json
# Args: $1 = field name (dot notation supported via jq)
get_state() {
  local field="$1"
  local state_file="$SYNC_DIR/state/session_state.json"
  if [[ -f "$state_file" ]]; then
    jq -r ".$field // empty" "$state_file" 2>/dev/null || echo ""
  else
    echo ""
  fi
}

# Update a field in session_state.json
# Args: $1 = field name, $2 = value
set_state() {
  local field="$1"
  local value="$2"
  local state_file="$SYNC_DIR/state/session_state.json"
  local tmp="${state_file}.tmp"
  jq --arg v "$value" ".$field = \$v" "$state_file" > "$tmp" && mv "$tmp" "$state_file"
}

# Get current timestamp in ISO format
now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Get current timestamp for display
now_display() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Format a notification message
# Args: $1 = type (notification|stop), $2 = message content
format_notification() {
  local type="$1"
  local content="$2"
  local project
  project="$(basename "$(pwd)")"
  local task
  task="$(get_state current_task)"
  local time
  time="$(now_display)"

  local header=""
  local body=""

  case "$type" in
    notification)
      # Detect notification subtype from content
      if echo "$content" | grep -qiE "等待|确认|confirm|waiting"; then
        header="⏸️ 等待确认"
        body="❓ ${content}"
      elif echo "$content" | grep -qiE "错误|失败|error|fail"; then
        header="❌ 任务中断"
        body="📋 任务：${task:-未指定}\n⚠️ ${content}"
      else
        header="🚀 Claude Code 通知"
        body="📋 ${content}"
      fi
      ;;
    stop)
      header="✅ Claude Code 已停止"
      if [[ -n "$task" ]]; then
        body="📋 最近任务：${task}"
      else
        body="会话已结束"
      fi
      ;;
    *)
      header="📢 Claude Code"
      body="$content"
      ;;
  esac

  # Assemble full message
  local msg
  msg="${header}\n\n${body}\n📁 项目：${project}\n⏰ ${time}"
  msg="${msg}\n\n---\n💡 回复指令：继续 | 进度 | 停下来 | 或输入具体需求"

  echo "$msg"
}

# Format a status reply (sent when user queries progress)
format_status_reply() {
  local state_file="$SYNC_DIR/state/session_state.json"

  if [[ ! -f "$state_file" ]]; then
    echo "⚠️ 无会话状态"
    return
  fi

  local status
  status="$(jq -r '.status // "unknown"' "$state_file")"
  local task
  task="$(jq -r '.current_task // "无"' "$state_file")"
  local summary
  summary="$(jq -r '.last_output_summary // ""' "$state_file")"
  local started
  started="$(jq -r '.started_at // ""' "$state_file")"
  local last_update
  last_update="$(jq -r '.last_update // ""' "$state_file")"

  local status_emoji="❓"
  case "$status" in
    working) status_emoji="🔄" ;;
    waiting) status_emoji="⏸️" ;;
    error)   status_emoji="❌" ;;
    idle)    status_emoji="💤" ;;
  esac

  local msg="📊 当前进度 — $(basename "$(pwd)")\n\n"
  msg="${msg}${status_emoji} 状态：${status}\n"
  msg="${msg}📋 任务：${task}\n"

  if [[ -n "$summary" ]]; then
    msg="${msg}📝 最近操作：${summary}\n"
  fi

  # Show todos if available
  local todo_count
  todo_count="$(jq '.todos | length' "$state_file" 2>/dev/null || echo 0)"
  if [[ "$todo_count" -gt 0 ]]; then
    msg="${msg}\n"
    # Parse todos and format
    while IFS= read -r todo_json; do
      local t_content t_status t_emoji
      t_content="$(echo "$todo_json" | jq -r '.content // ""')"
      t_status="$(echo "$todo_json" | jq -r '.status // "pending"')"
      case "$t_status" in
        completed)   t_emoji="✅" ;;
        in_progress) t_emoji="🔄" ;;
        *)           t_emoji="⏳" ;;
      esac
      msg="${msg}${t_emoji} ${t_content}\n"
    done < <(jq -c '.todos[]' "$state_file" 2>/dev/null)
  fi

  msg="${msg}\n⏰ 更新于：${last_update:-未知}"
  msg="${msg}\n\n---\n💡 回复指令：继续 | 停下来 | 或输入具体需求"

  echo "$msg"
}
```

- [ ] **Step 2: Verify syntax**

Run:
```bash
bash -n .claude/feishu-sync/bin/format-message.sh && echo "✅ Syntax OK"
```
Expected: `✅ Syntax OK`

- [ ] **Step 3: Test format functions manually**

Run:
```bash
source .claude/feishu-sync/bin/format-message.sh
format_notification notification "正在实现用户登录功能"
echo "---"
format_notification stop ""
echo "---"
format_status_reply
```
Expected: Formatted messages with emoji and project name

- [ ] **Step 4: Commit**

```bash
git add .claude/feishu-sync/bin/format-message.sh
git commit -m "feat(feishu-sync): add message formatting utility"
```

---

## Task 3: Notification Sender Script

**Files:**
- Create: `.claude/feishu-sync/bin/send-notification.sh`

This is the main script called by Claude Code hooks. It receives a notification type and content, formats it, and sends it to Feishu.

- [ ] **Step 1: Create send-notification.sh**

```bash
#!/usr/bin/env bash
# .claude/feishu-sync/bin/send-notification.sh
# Called by Claude Code hooks to send notifications to Feishu.
# Usage: send-notification.sh <type> [content]
#   type: notification | stop
#   content: the notification text (optional for stop)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SYNC_DIR/config.json"
STATE_FILE="$SYNC_DIR/state/session_state.json"

# Source formatting utilities
source "$SCRIPT_DIR/format-message.sh"

TYPE="${1:-notification}"
CONTENT="${2:-}"

# Read chat_id from config
CHAT_ID=""
if [[ -f "$CONFIG_FILE" ]]; then
  CHAT_ID="$(jq -r '.feishu_chat_id // empty' "$CONFIG_FILE")"
fi

if [[ -z "$CHAT_ID" ]]; then
  echo "⚠️  feishu_chat_id not configured. Run setup.sh first." >&2
  exit 0  # Don't block the hook
fi

# Truncate very long content
if [[ ${#CONTENT} -gt 1000 ]]; then
  CONTENT="${CONTENT:0:997}..."
fi

# Format the message
MSG="$(format_notification "$TYPE" "$CONTENT")"

# Update session state
if [[ -f "$STATE_FILE" ]]; then
  local_timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  case "$TYPE" in
    notification)
      # Update status based on content
      if echo "$CONTENT" | grep -qiE "等待|确认|confirm|waiting"; then
        jq --arg ts "$local_timestamp" '.status = "waiting" | .last_update = $ts' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
      elif echo "$CONTENT" | grep -qiE "错误|失败|error|fail"; then
        jq --arg ts "$local_timestamp" --arg c "$CONTENT" '.status = "error" | .last_update = $ts | .last_output_summary = $c' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
      else
        jq --arg ts "$local_timestamp" --arg c "$CONTENT" '.status = "working" | .last_update = $ts | .current_task = $c' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
      fi
      ;;
    stop)
      jq --arg ts "$local_timestamp" '.status = "idle" | .last_update = $ts' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
      ;;
  esac
fi

# Send to Feishu
RESPONSE="$(lark-cli im +messages-send --chat-id "$CHAT_ID" --text "$MSG" --as bot 2>&1 || true)"

# Extract and save the message_id for future replies
MSG_ID=""
if [[ -n "$RESPONSE" ]]; then
  MSG_ID="$(echo "$RESPONSE" | jq -r '.data.message_id // empty' 2>/dev/null || true)"
fi

if [[ -n "$MSG_ID" && -f "$STATE_FILE" ]]; then
  jq --arg mid "$MSG_ID" '.last_feishu_msg_id = $mid' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
fi

echo "✅ Notification sent to Feishu (type=$TYPE)"
```

- [ ] **Step 2: Make executable and verify syntax**

Run:
```bash
chmod +x .claude/feishu-sync/bin/send-notification.sh
bash -n .claude/feishu-sync/bin/send-notification.sh && echo "✅ Syntax OK"
```
Expected: `✅ Syntax OK`

- [ ] **Step 3: Test manual notification**

Run:
```bash
.claude/feishu-sync/bin/send-notification.sh notification "测试：正在实现飞书同步插件"
```
Expected: `✅ Notification sent to Feishu (type=notification)` and a message appears in the Feishu group

- [ ] **Step 4: Verify session_state.json updated**

Run:
```bash
cat .claude/feishu-sync/state/session_state.json | jq '{status, current_task, last_update}'
```
Expected: `status` = `"working"`, `current_task` contains the test message, `last_update` is recent

- [ ] **Step 5: Test stop notification**

Run:
```bash
.claude/feishu-sync/bin/send-notification.sh stop
```
Expected: Stop message sent to Feishu, session_state.json status updated to `"idle"`

- [ ] **Step 6: Commit**

```bash
git add .claude/feishu-sync/bin/send-notification.sh
git commit -m "feat(feishu-sync): add notification sender script"
```

---

## Task 4: Command Polling Script

**Files:**
- Create: `.claude/feishu-sync/bin/poll-commands.sh`

Reads new messages from the Feishu group, filters for user commands, parses them, and writes to the command queue.

- [ ] **Step 1: Create poll-commands.sh**

```bash
#!/usr/bin/env bash
# .claude/feishu-sync/bin/poll-commands.sh
# Polls Feishu for new messages and writes parsed commands to the queue.
# Usage: poll-commands.sh [--count N]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SYNC_DIR/config.json"
STATE_FILE="$SYNC_DIR/state/session_state.json"
QUEUE_FILE="$SYNC_DIR/queue/commands.jsonl"

# Read config
CHAT_ID=""
ALLOWED_USERS=""
MAX_CMD_LEN=500
FETCH_COUNT="${1:-20}"

if [[ -f "$CONFIG_FILE" ]]; then
  CHAT_ID="$(jq -r '.feishu_chat_id // empty' "$CONFIG_FILE")"
  MAX_CMD_LEN="$(jq -r '.max_command_length // 500' "$CONFIG_FILE")"
  ALLOWED_USERS="$(jq -r '.allowed_user_ids | join(",")' "$CONFIG_FILE" 2>/dev/null || true)"
fi

if [[ -z "$CHAT_ID" ]]; then
  echo "⚠️  chat_id not configured" >&2
  exit 0
fi

# Get last polled timestamp
LAST_TS="0"
if [[ -f "$STATE_FILE" ]]; then
  LAST_TS="$(jq -r '.last_polled_msg_ts // "0"' "$STATE_FILE")"
fi

# Fetch recent messages from Feishu
MESSAGES=""
MESSAGES="$(lark-cli im +chat-messages-list --chat-id "$CHAT_ID" --page-size "$FETCH_COUNT" --format json 2>/dev/null || echo '{"items":[]}')"

# Parse messages and find new commands
NEW_COUNT=0
LATEST_TS="$LAST_TS"

# Process each message
while IFS= read -r msg; do
  [[ -z "$msg" ]] && continue

  msg_id="$(echo "$msg" | jq -r '.message_id // empty')"
  msg_ts="$(echo "$msg" | jq -r '.create_time // "0"')"
  sender_type="$(echo "$msg" | jq -r '.sender.sender_type // empty')"
  sender_id="$(echo "$msg" | jq -r '.sender.sender_id.open_id // empty' 2>/dev/null || echo "")"
  msg_type="$(echo "$msg" | jq -r '.msg_type // empty')"
  body_content="$(echo "$msg" | jq -r '.body.content // empty' 2>/dev/null || echo "")"

  # Skip old messages
  if [[ "$msg_ts" -le "$LAST_TS" ]] 2>/dev/null; then
    continue
  fi

  # Update latest timestamp
  if [[ "$msg_ts" -gt "$LATEST_TS" ]] 2>/dev/null; then
    LATEST_TS="$msg_ts"
  fi

  # Skip bot messages (we only want human commands)
  if [[ "$sender_type" == "bot" ]]; then
    continue
  fi

  # Skip non-text messages
  if [[ "$msg_type" != "text" ]]; then
    continue
  fi

  # Filter by allowed users (if configured)
  if [[ -n "$ALLOWED_USERS" && -n "$sender_id" ]]; then
    if ! echo ",$ALLOWED_USERS," | grep -q ",$sender_id,"; then
      continue
    fi
  fi

  # Extract text content from body JSON
  text=""
  text="$(echo "$body_content" | jq -r '.text // empty' 2>/dev/null || echo "$body_content")"

  # Skip empty or too-long messages
  if [[ -z "$text" || ${#text} -gt "$MAX_CMD_LEN" ]]; then
    continue
  fi

  # Skip messages that look like bot responses (contain specific markers)
  if echo "$text" | grep -qE "^(🚀|✅|❌|⏸️|📊|📢|💡)"; then
    continue
  fi

  # Parse command type
  cmd_type="requirement"
  cmd_parsed="null"
  cmd_id="cmd_$(date +%s)_$((RANDOM % 1000))"

  # Short commands
  case "$text" in
    继续|continue|go|go\ on|继续工作)
      cmd_type="short_command"
      cmd_parsed='"continue"'
      ;;
    停|暂停|stop|wait|pause|停下来)
      cmd_type="short_command"
      cmd_parsed='"pause"'
      ;;
    重新来|重来|redo|restart|重来一次)
      cmd_type="short_command"
      cmd_parsed='"restart"'
      ;;
    换个方案|换方案|try\ another|换个方式)
      cmd_type="short_command"
      cmd_parsed='"try_alternative"'
      ;;
    确认|ok|yes|好的|可以|confirm)
      cmd_type="short_command"
      cmd_parsed='"confirm"'
      ;;
    取消|no|不要|cancel|算了)
      cmd_type="short_command"
      cmd_parsed='"cancel"'
      ;;
  esac

  # Status queries
  if echo "$text" | grep -qiE "^(进度|状态|status|progress|现在|当前|在干嘛|怎么样了|做了什么)"; then
    cmd_type="status_query"
    cmd_parsed='"status_query"'
  fi

  # Flow control (has keywords but not exact match)
  if [[ "$cmd_type" == "requirement" ]]; then
    if echo "$text" | grep -qiE "^(先做|跳过|优先|先|skip|做|任务)"; then
      cmd_type="flow_control"
    fi
  fi

  # Write to queue
  local_ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if [[ "$cmd_parsed" == "null" ]]; then
    jq -nc \
      --arg id "$cmd_id" \
      --arg ts "$local_ts" \
      --arg type "$cmd_type" \
      --arg raw "$text" \
      '{id: $id, ts: $ts, type: $type, raw: $raw, status: "pending"}'
  else
    jq -nc \
      --arg id "$cmd_id" \
      --arg ts "$local_ts" \
      --arg type "$cmd_type" \
      --arg raw "$text" \
      --argjson parsed "$cmd_parsed" \
      '{id: $id, ts: $ts, type: $type, raw: $raw, parsed: $parsed, status: "pending"}'
  fi >> "$QUEUE_FILE"

  NEW_COUNT=$((NEW_COUNT + 1))

done < <(echo "$MESSAGES" | jq -c '.items[] // empty' 2>/dev/null)

# Update last polled timestamp
if [[ -f "$STATE_FILE" && "$LATEST_TS" != "$LAST_TS" ]]; then
  jq --arg ts "$LATEST_TS" '.last_polled_msg_ts = $ts' "$STATE_FILE" > "${STATE_FILE}.tmp" && mv "${STATE_FILE}.tmp" "$STATE_FILE"
fi

echo "✅ Polled: ${NEW_COUNT} new command(s) found"
```

- [ ] **Step 2: Make executable and verify syntax**

Run:
```bash
chmod +x .claude/feishu-sync/bin/poll-commands.sh
bash -n .claude/feishu-sync/bin/poll-commands.sh && echo "✅ Syntax OK"
```
Expected: `✅ Syntax OK`

- [ ] **Step 3: Test polling (send a test message from Feishu first)**

First, send a message like "进度" from your Feishu account to the group. Then:

Run:
```bash
.claude/feishu-sync/bin/poll-commands.sh
```
Expected: `✅ Polled: 1 new command(s) found` (or similar)

- [ ] **Step 4: Verify command queue**

Run:
```bash
cat .claude/feishu-sync/queue/commands.jsonl
```
Expected: JSON line with the message you sent, type parsed correctly

- [ ] **Step 5: Commit**

```bash
git add .claude/feishu-sync/bin/poll-commands.sh
git commit -m "feat(feishu-sync): add command polling script"
```

---

## Task 5: Hooks Configuration

**Files:**
- Modify: `.claude/settings.local.json`

Configure Claude Code hooks to call send-notification.sh on Notification and Stop events.

- [ ] **Step 1: Read current settings.local.json**

Run:
```bash
cat .claude/settings.local.json
```
Note the current content — we will add a `hooks` key.

- [ ] **Step 2: Add hooks configuration**

Add the following `hooks` key to `.claude/settings.local.json`. The existing `permissions` content stays unchanged — only the `hooks` key is new:

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/feishu-sync/bin/send-notification.sh notification \"$CLAUDE_NOTIFICATION\"",
            "timeout": 15
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
            "command": "bash .claude/feishu-sync/bin/send-notification.sh stop",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

The `permissions` key from the existing file stays unchanged. Only the `hooks` key is added alongside it.

- [ ] **Step 3: Verify hooks are registered**

Start a new Claude Code session and trigger a notification event. Or verify manually:

Run:
```bash
# Quick syntax check of the JSON
jq . .claude/settings.local.json > /dev/null && echo "✅ Valid JSON"
jq '.hooks | keys' .claude/settings.local.json
```
Expected: `["Notification", "Stop"]`

- [ ] **Step 4: Commit**

```bash
git add .claude/settings.local.json
git commit -m "feat(feishu-sync): configure Notification and Stop hooks"
```

---

## Task 6: Command Consumer (CronCreate Prompt)

This task sets up the CronCreate job that periodically polls for commands and processes them. There is no file to create — this is a runtime configuration done via the CronCreate tool.

- [ ] **Step 1: Start the polling cron job**

Use CronCreate to set up periodic polling:

```
CronCreate:
  cron: "*/3 9-23 * * 1-5"
  prompt: |
    检查远程指令队列：
    1. 运行 `.claude/feishu-sync/bin/poll-commands.sh` 拉取飞书新消息
    2. 读取 `.claude/feishu-sync/queue/commands.jsonl` 中 status=pending 的记录
    3. 如果没有 pending 指令，不做任何事，直接结束
    4. 如果有 pending 指令，按顺序处理：
       a. short_command (continue/pause/confirm/cancel 等):
          - continue: 继续当前工作
          - pause: 暂停，等待用户回来
          - restart: 重新执行最近的任务
          - confirm: 确认当前等待的操作
          - cancel: 取消当前等待的操作
       b. flow_control: 解析并调整任务优先级
       c. status_query: 读取 .claude/feishu-sync/state/session_state.json，调用 send-notification.sh 回复状态
       d. requirement: 直接作为新的 prompt 执行
    5. 处理完每条指令后：
       - 从 commands.jsonl 中移除
       - 追加到 processed.jsonl 并标记 status=completed
    6. 通过 `.claude/feishu-sync/bin/send-notification.sh notification "✅ 已处理远程指令：{指令摘要}"` 回复结果
  recurring: true
```

Cron schedule `*/3 9-23 * * 1-5` means: every 3 minutes, 9am to 11pm, Monday to Friday.

- [ ] **Step 2: Verify cron is running**

Run CronList to confirm the job is active.

- [ ] **Step 3: End-to-end test**

1. From Feishu, send "进度？" to the group
2. Wait up to 3 minutes for the cron to fire
3. Verify the queue file has a new entry
4. Verify Claude processes it and sends back a status reply to Feishu

---

## Task 7: End-to-End Verification

- [ ] **Step 1: Verify outbound notification**

In Claude Code, perform any action that triggers a notification (e.g., complete a task). Check Feishu group for the notification message.

- [ ] **Step 2: Verify stop notification**

Let Claude Code finish and stop. Check Feishu group for the stop message.

- [ ] **Step 3: Verify inbound short command**

From Feishu, send "继续". Wait for cron. Verify Claude receives and acts on it.

- [ ] **Step 4: Verify inbound status query**

From Feishu, send "进度？". Wait for cron. Verify a formatted status reply appears in Feishu.

- [ ] **Step 5: Verify inbound requirement**

From Feishu, send "把按钮颜色改成蓝色". Wait for cron. Verify Claude treats it as a new task.

- [ ] **Step 6: Final commit**

```bash
git add -A .claude/feishu-sync/
git commit -m "feat(feishu-sync): complete bidirectional Feishu session sync plugin"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Each section of the spec maps to a task:
  - File structure → Tasks 1–4
  - Outbound notifications → Task 3 (send-notification.sh) + Task 5 (hooks)
  - Inbound commands → Task 4 (poll-commands.sh) + Task 6 (CronCreate)
  - Session state → Tasks 1–3 (created and updated)
  - Security → Task 4 (user filtering, length limit)
  - Config → Task 1 (setup.sh)
- [x] **Placeholder scan:** No TBD/TODO/placeholder patterns found
- [x] **Type consistency:** JSONL format (id, ts, type, raw, parsed, status) used consistently across Task 4 (writer) and Task 6 (reader)
