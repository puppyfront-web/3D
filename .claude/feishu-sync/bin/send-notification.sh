#!/usr/bin/env bash
# .claude/feishu-sync/bin/send-notification.sh
# Called by Claude Code hooks to send notifications to Feishu.
# Multi-session aware, uses interactive card format.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SYNC_DIR/config.json"

# Source formatting utilities (multi-session aware)
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
  exit 0
fi

# Truncate very long content
if [[ ${#CONTENT} -gt 1000 ]]; then
  CONTENT="${CONTENT:0:997}..."
fi

# Format the message as interactive card JSON
MSG="$(format_notification "$TYPE" "$CONTENT")"

# Update session state
local_timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

case "$TYPE" in
  notification)
    if echo "$CONTENT" | grep -qiE "等待|确认|confirm|waiting"; then
      set_state "status" "waiting"
    elif echo "$CONTENT" | grep -qiE "错误|失败|error|fail"; then
      set_state "status" "error"
      set_state "last_output_summary" "$CONTENT"
    else
      set_state "status" "working"
      set_state "current_task" "$CONTENT"
    fi
    set_state "last_update" "$local_timestamp"
    ;;
  stop)
    set_state "status" "stopped"
    set_state "last_update" "$local_timestamp"
    ;;
esac

# Send to Feishu as interactive card
RESPONSE="$(lark-cli im +messages-send --chat-id "$CHAT_ID" --msg-type interactive --content "$MSG" --as bot 2>&1 || true)"

# Extract and save message_id
MSG_ID=""
if [[ -n "$RESPONSE" ]]; then
  MSG_ID="$(echo "$RESPONSE" | jq -r '.data.message_id // empty' 2>/dev/null || true)"
fi

if [[ -n "$MSG_ID" ]]; then
  set_state "last_feishu_msg_id" "$MSG_ID"
fi

echo "✅ Card notification sent to Feishu (type=$TYPE, session=$(current_session_id))"
