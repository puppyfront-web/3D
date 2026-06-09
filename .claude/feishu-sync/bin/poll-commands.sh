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
