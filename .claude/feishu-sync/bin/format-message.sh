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
