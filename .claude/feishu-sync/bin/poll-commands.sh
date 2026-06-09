#!/usr/bin/env bash
# .claude/feishu-sync/bin/poll-commands.sh
# Polls Feishu for new messages and writes parsed commands to the queue.
# Multi-session aware: routes commands to the correct session.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SYNC_DIR/config.json"
SESSIONS_FILE="$SYNC_DIR/state/sessions.json"
QUEUE_FILE="$SYNC_DIR/queue/commands.jsonl"

# Source formatting utilities
source "$SCRIPT_DIR/format-message.sh"

# Read config
CHAT_ID=""
ALLOWED_USERS=""
MAX_CMD_LEN=500
FETCH_COUNT=20

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
if [[ -f "$SESSIONS_FILE" ]]; then
  LAST_TS="$(jq -r '.last_polled_msg_ts // "0"' "$SESSIONS_FILE")"
fi

# Fetch recent messages from Feishu
MESSAGES=""
MESSAGES="$(lark-cli im +chat-messages-list --chat-id "$CHAT_ID" --page-size "$FETCH_COUNT" --as bot 2>/dev/null || echo '{"data":{"messages":[]}}')"

# Parse messages and find new commands
NEW_COUNT=0
LATEST_TS="$LAST_TS"

while IFS= read -r msg; do
  [[ -z "$msg" ]] && continue

  msg_id="$(echo "$msg" | jq -r '.message_id // empty')"
  msg_ts="$(echo "$msg" | jq -r '.create_time // "0"')"
  sender_type="$(echo "$msg" | jq -r '.sender.sender_type // empty')"
  sender_id="$(echo "$msg" | jq -r '.sender.id // empty' 2>/dev/null || echo "")"
  msg_type="$(echo "$msg" | jq -r '.msg_type // empty')"
  body_content="$(echo "$msg" | jq -r '.content // empty' 2>/dev/null || echo "")"

  # Skip old messages (string comparison works for "YYYY-MM-DD HH:MM" format)
  if [[ "$msg_ts" == "$LAST_TS" || "$msg_ts" < "$LAST_TS" ]]; then
    continue
  fi

  # Update latest timestamp
  if [[ -z "$LATEST_TS" || "$LATEST_TS" == "0" || "$msg_ts" > "$LATEST_TS" ]]; then
    LATEST_TS="$msg_ts"
  fi

  # Skip bot/app messages
  if [[ "$sender_type" == "app" || "$sender_type" == "bot" ]]; then
    continue
  fi

  # Skip non-text messages
  if [[ "$msg_type" != "text" ]]; then
    continue
  fi

  # Filter by allowed users
  if [[ -n "$ALLOWED_USERS" && -n "$sender_id" ]]; then
    if ! echo ",$ALLOWED_USERS," | grep -q ",$sender_id,"; then
      continue
    fi
  fi

  # Extract text content
  text=""
  text="$(echo "$body_content" | jq -r '.text // empty' 2>/dev/null || echo "$body_content")"

  # Skip empty or too-long messages
  if [[ -z "$text" || ${#text} -gt "$MAX_CMD_LEN" ]]; then
    continue
  fi

  # Skip bot response markers
  if echo "$text" | grep -qE "^(🚀|✅|❌|⏸️|📊|📢|💡|💤|🤖)"; then
    continue
  fi

  # Parse command type
  cmd_type="requirement"
  cmd_parsed="null"
  cmd_session="auto"
  cmd_id="cmd_$(date +%s)_$((RANDOM % 1000))"

  # Check for session targeting: "1 xxx" or "@项目名 xxx"
  if echo "$text" | grep -qiE "^[0-9]+ "; then
    # "1 继续" format - extract session number
    target_num="$(echo "$text" | grep -oE "^[0-9]+")"
    cmd_session="idx:${target_num}"
    text="$(echo "$text" | sed "s/^[0-9]* //")"
  elif echo "$text" | grep -qiE "^@"; then
    # "@项目名 指令" format
    target_name="$(echo "$text" | sed 's/^@//;s/ .*//')"
    cmd_session="name:${target_name}"
    text="$(echo "$text" | sed 's/^@[^ ]* //')"
  fi

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

  # Session listing commands
  if echo "$text" | grep -qiE "^(会话|sessions|列表|全部)"; then
    cmd_type="session_list"
    cmd_parsed='"session_list"'
  fi

  # Status queries
  if [[ "$cmd_type" == "requirement" ]]; then
    if echo "$text" | grep -qiE "^(进度|状态|status|progress|现在|当前|在干嘛|怎么样了|做了什么)"; then
      cmd_type="status_query"
      cmd_parsed='"status_query"'
    fi
  fi

  # Flow control
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
      --arg session "$cmd_session" \
      '{id: $id, ts: $ts, type: $type, raw: $raw, session: $session, status: "pending"}'
  else
    jq -nc \
      --arg id "$cmd_id" \
      --arg ts "$local_ts" \
      --arg type "$cmd_type" \
      --arg raw "$text" \
      --argjson parsed "$cmd_parsed" \
      --arg session "$cmd_session" \
      '{id: $id, ts: $ts, type: $type, raw: $raw, parsed: $parsed, session: $session, status: "pending"}'
  fi >> "$QUEUE_FILE"

  NEW_COUNT=$((NEW_COUNT + 1))

done < <(echo "$MESSAGES" | jq -c '.data.messages[] // empty' 2>/dev/null)

# Update last polled timestamp
ensure_sessions_file
if [[ "$LATEST_TS" != "$LAST_TS" ]]; then
  local tmp="${SESSIONS_FILE}.tmp"
  jq --arg ts "$LATEST_TS" '.last_polled_msg_ts = $ts' "$SESSIONS_FILE" > "$tmp" && mv "$tmp" "$SESSIONS_FILE"
fi

echo "✅ Polled: ${NEW_COUNT} new command(s) found"
