#!/usr/bin/env bash
# .claude/feishu-sync/bin/format-message.sh
# Shared message formatting functions for multi-session support.
# Sourced by other scripts.

SYNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSIONS_FILE="$SYNC_DIR/state/sessions.json"

# Ensure sessions.json exists
ensure_sessions_file() {
  if [[ ! -f "$SESSIONS_FILE" ]]; then
    echo '{"sessions":{}}' > "$SESSIONS_FILE"
  fi
}

# Get current session ID from project directory
current_session_id() {
  basename "$(pwd)"
}

# Read a field from current session
# Args: $1 = field name
get_state() {
  local field="$1"
  local sid
  sid="$(current_session_id)"
  ensure_sessions_file
  jq -r ".sessions[\"$sid\"].$field // empty" "$SESSIONS_FILE" 2>/dev/null || echo ""
}

# Read a field from a specific session
# Args: $1 = session_id, $2 = field name
get_session_state() {
  local sid="$1"
  local field="$2"
  ensure_sessions_file
  jq -r ".sessions[\"$sid\"].$field // empty" "$SESSIONS_FILE" 2>/dev/null || echo ""
}

# Update a field in current session
# Args: $1 = field name, $2 = value
set_state() {
  local field="$1"
  local value="$2"
  local sid
  sid="$(current_session_id)"
  local tmp="${SESSIONS_FILE}.tmp"
  ensure_sessions_file
  jq --arg sid "$sid" --arg v "$value" "
    .sessions[\"$sid\"] = (.sessions[\"$sid\"] // {\"project\": \"$sid\", \"status\": \"idle\"}) |
    .sessions[\"$sid\"].$field = \$v
  " "$SESSIONS_FILE" > "$tmp" && mv "$tmp" "$SESSIONS_FILE"
}

# Get the most recently updated session ID
# Returns: session_id or empty
latest_session_id() {
  ensure_sessions_file
  jq -r '[.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped")] | sort_by(.value.last_update) | last | .key // empty' "$SESSIONS_FILE" 2>/dev/null || echo ""
}

# List all active (non-idle) sessions
# Returns: formatted list string
list_active_sessions() {
  ensure_sessions_file
  local count
  count="$(jq '[.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped")] | length' "$SESSIONS_FILE" 2>/dev/null || echo 0)"

  if [[ "$count" -eq 0 ]]; then
    echo "💤 没有活跃的 Claude Code 会话"
    return
  fi

  local msg="📊 活跃会话 (${count}个)：\n"
  local idx=1
  while IFS= read -r entry; do
    local sid status task last_update emoji
    sid="$(echo "$entry" | jq -r '.key')"
    status="$(echo "$entry" | jq -r '.value.status // "unknown"')"
    task="$(echo "$entry" | jq -r '.value.current_task // "无任务"')"
    last_update="$(echo "$entry" | jq -r '.value.last_update // ""')"
    case "$status" in
      working) emoji="🔄" ;;
      waiting) emoji="⏸️" ;;
      error)   emoji="❌" ;;
      *)       emoji="❓" ;;
    esac
    msg="${msg}  ${idx}. ${emoji} [${sid}] ${task}\n"
    idx=$((idx + 1))
  done < <(jq -c '.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped") | sort_by(.value.last_update)' "$SESSIONS_FILE" 2>/dev/null)

  msg="${msg}\n💡 回复 \"1 继续\" 或 \"@${sid} 进度\" 指定会话"
  echo "$msg"
}

# Get current timestamp for display
now_display() {
  date +"%Y-%m-%d %H:%M:%S"
}

# Format a notification message with project prefix
# Args: $1 = type (notification|stop), $2 = message content
format_notification() {
  local type="$1"
  local content="$2"
  local project
  project="$(current_session_id)"
  local task
  task="$(get_state current_task)"
  local time
  time="$(now_display)"

  local header=""
  local body=""

  case "$type" in
    notification)
      if echo "$content" | grep -qiE "等待|确认|confirm|waiting"; then
        header="⏸️ [${project}] 等待确认"
        body="❓ ${content}"
      elif echo "$content" | grep -qiE "错误|失败|error|fail"; then
        header="❌ [${project}] 任务中断"
        body="📋 任务：${task:-未指定}\n⚠️ ${content}"
      else
        header="🚀 [${project}]"
        body="📋 ${content}"
      fi
      ;;
    stop)
      header="✅ [${project}] 已停止"
      if [[ -n "$task" ]]; then
        body="📋 最近任务：${task}"
      else
        body="会话已结束"
      fi
      ;;
    *)
      header="📢 [${project}]"
      body="$content"
      ;;
  esac

  local msg="${header}\n\n${body}\n⏰ ${time}"
  msg="${msg}\n\n---\n💡 回复指令：继续 | 进度 | 停下来 | 或输入具体需求"

  echo "$msg"
}

# Format a status reply for a specific session
# Args: $1 = session_id (optional, defaults to current)
format_status_reply() {
  local sid="${1:-}"
  if [[ -z "$sid" ]]; then
    sid="$(current_session_id)"
  fi

  ensure_sessions_file

  local status task summary last_update
  status="$(jq -r ".sessions[\"$sid\"].status // \"unknown\"" "$SESSIONS_FILE")"
  task="$(jq -r ".sessions[\"$sid\"].current_task // \"无\"" "$SESSIONS_FILE")"
  summary="$(jq -r ".sessions[\"$sid\"].last_output_summary // \"\"" "$SESSIONS_FILE")"
  last_update="$(jq -r ".sessions[\"$sid\"].last_update // \"\"" "$SESSIONS_FILE")"

  local status_emoji="❓"
  case "$status" in
    working) status_emoji="🔄" ;;
    waiting) status_emoji="⏸️" ;;
    error)   status_emoji="❌" ;;
    idle)    status_emoji="💤" ;;
  esac

  local msg="📊 [${sid}] 当前进度\n\n"
  msg="${msg}${status_emoji} 状态：${status}\n"
  msg="${msg}📋 任务：${task}\n"

  if [[ -n "$summary" ]]; then
    msg="${msg}📝 最近操作：${summary}\n"
  fi

  local todo_count
  todo_count="$(jq ".sessions[\"$sid\"].todos | length" "$SESSIONS_FILE" 2>/dev/null || echo 0)"
  if [[ "$todo_count" -gt 0 ]]; then
    msg="${msg}\n"
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
    done < <(jq -c ".sessions[\"$sid\"].todos[]" "$SESSIONS_FILE" 2>/dev/null)
  fi

  msg="${msg}\n⏰ 更新于：${last_update:-未知}"
  msg="${msg}\n\n---\n💡 回复指令：继续 | 停下来 | 或输入具体需求"

  echo "$msg"
}
