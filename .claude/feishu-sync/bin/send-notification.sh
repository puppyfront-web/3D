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
