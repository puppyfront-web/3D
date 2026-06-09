#!/usr/bin/env bash
# .claude/feishu-sync/bin/check-commands-throttled.sh
# PostToolUse hook: throttled check for Feishu commands.
# Only polls if 120+ seconds have passed since last check.
# Called automatically after every Claude tool use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_DIR="$(dirname "$SCRIPT_DIR")"
LAST_CHECK_FILE="$SYNC_DIR/state/last_check_ts"
THROTTLE_SECONDS=120

# Read last check timestamp
LAST_CHECK=0
if [[ -f "$LAST_CHECK_FILE" ]]; then
  LAST_CHECK="$(cat "$LAST_CHECK_FILE" 2>/dev/null || echo 0)"
fi

# Current time in seconds since epoch
NOW="$(date +%s)"

# Check throttle
ELAPSED=$((NOW - LAST_CHECK))
if [[ "$ELAPSED" -lt "$THROTTLE_SECONDS" ]]; then
  # Not enough time passed, skip silently
  exit 0
fi

# Update last check timestamp
echo "$NOW" > "$LAST_CHECK_FILE"

# Poll for new commands (output to stderr so it doesn't interfere with hook stdout)
bash "$SCRIPT_DIR/poll-commands.sh" >&2 || true

# Check if there are pending commands
QUEUE_FILE="$SYNC_DIR/queue/commands.jsonl"
if [[ ! -f "$QUEUE_FILE" ]] || ! grep -q '"status":"pending"' "$QUEUE_FILE" 2>/dev/null; then
  exit 0
fi

# There are pending commands — output JSON to tell Claude to process them
# This becomes a systemMessage injected into Claude's context
jq -nc '{systemMessage: "📬 飞书收到新的远程指令，请检查 .claude/feishu-sync/queue/commands.jsonl 并处理 pending 指令。处理完后回复飞书。"}'
