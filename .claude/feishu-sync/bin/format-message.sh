#!/usr/bin/env bash
# .claude/feishu-sync/bin/format-message.sh
# Shared message formatting functions for multi-session support.
# Outputs Feishu interactive card JSON.
# Sourced by other scripts.

SYNC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSIONS_FILE="$SYNC_DIR/state/sessions.json"

# ============================================================
# State Management Functions (unchanged)
# ============================================================

ensure_sessions_file() {
  if [[ ! -f "$SESSIONS_FILE" ]]; then
    echo '{"sessions":{}}' > "$SESSIONS_FILE"
  fi
}

current_session_id() {
  basename "$(pwd)"
}

get_state() {
  local field="$1"
  local sid
  sid="$(current_session_id)"
  ensure_sessions_file
  jq -r ".sessions[\"$sid\"].$field // empty" "$SESSIONS_FILE" 2>/dev/null || echo ""
}

get_session_state() {
  local sid="$1"
  local field="$2"
  ensure_sessions_file
  jq -r ".sessions[\"$sid\"].$field // empty" "$SESSIONS_FILE" 2>/dev/null || echo ""
}

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

latest_session_id() {
  ensure_sessions_file
  jq -r '[.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped")] | sort_by(.value.last_update) | last | .key // empty' "$SESSIONS_FILE" 2>/dev/null || echo ""
}

now_display() {
  date +"%Y-%m-%d %H:%M:%S"
}

# ============================================================
# Card JSON Builder Helpers
# ============================================================

# Build a card header element
# Args: $1 = template color, $2 = title text
_card_header() {
  jq -nc \
    --arg template "$1" \
    --arg title "$2" \
    '{template: $template, title: {tag: "plain_text", content: $title}}'
}

# Build a field element (key-value pairs in columns)
# Args: $1 = JSON array of field objects [{"is_short":true,"text":{"tag":"lark_md","content":"**key**\nvalue"}}]
_card_fields() {
  local fields_json="$1"
  jq -nc --argjson fields "$fields_json" '{tag: "div", fields: $fields}'
}

# Build a markdown div element
# Args: $1 = markdown content
_card_md() {
  local content="$1"
  jq -nc --arg content "$content" '{tag: "div", text: {tag: "lark_md", content: $content}}'
}

# Build a divider
_card_hr() {
  echo '{"tag": "hr"}'
}

# Build an action element with buttons
# Args: $1 = JSON array of button objects
_card_actions() {
  local buttons_json="$1"
  jq -nc --argjson buttons "$buttons_json" '{tag: "action", actions: $buttons}'
}

# Build a note element
# Args: $1 = note text
_card_note() {
  local content="$1"
  jq -nc --arg content "$content" '{tag: "note", elements: [{tag: "plain_text", content: $content}]}'
}

# Build a single button
# Args: $1 = button text, $2 = button type (primary|default|danger), $3 = command value
_card_button() {
  local text="$1"
  local btype="${2:-default}"
  local cmd="$3"
  jq -nc \
    --arg text "$text" \
    --arg btype "$btype" \
    --arg cmd "$cmd" \
    '{tag: "button", text: {tag: "plain_text", content: $text}, type: $btype, value: {cmd: $cmd}}'
}

# Assemble a card from header + elements
# Args: $1 = header JSON, $2... = element JSONs
_build_card() {
  local header="$1"
  shift
  local elements="["
  local first=true
  for elem in "$@"; do
    if [[ -n "$elem" ]]; then
      if [[ "$first" == "true" ]]; then
        elements="${elements}${elem}"
        first=false
      else
        elements="${elements},${elem}"
      fi
    fi
  done
  elements="${elements}]"

  jq -nc \
    --argjson header "$header" \
    --argjson elements "$elements" \
    '{config: {wide_screen_mode: true}, header: $header, elements: $elements}'
}

# ============================================================
# Card Format Functions
# ============================================================

# Format a notification as a Feishu interactive card
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

  local header_color="turquoise"
  local header_title="🚀 [${project}] 正在工作"
  local body_md="📋 ${content}"
  local buttons="[]"

  case "$type" in
    notification)
      if echo "$content" | grep -qiE "等待|确认|confirm|waiting"; then
        header_color="orange"
        header_title="⏸️ [${project}] 等待确认"
        body_md="❓ ${content}"
        buttons="[$(_card_button "确认" "primary" "确认"),$(_card_button "取消" "danger" "取消")]"
      elif echo "$content" | grep -qiE "错误|失败|error|fail"; then
        header_color="red"
        header_title="❌ [${project}] 任务中断"
        body_md="📋 任务：${task:-未指定}\n⚠️ ${content}"
        buttons="[$(_card_button "重试" "primary" "重新来"),$(_card_button "换个方式" "default" "换个方案"),$(_card_button "查看进度" "default" "进度")]"
      else
        header_color="turquoise"
        header_title="🚀 [${project}] 正在工作"
        body_md="📋 ${content}"
        buttons="[$(_card_button "继续" "primary" "继续"),$(_card_button "暂停" "default" "停"),$(_card_button "查看进度" "default" "进度")]"
      fi
      ;;
    stop)
      header_color="green"
      header_title="✅ [${project}] 已停止"
      if [[ -n "$task" ]]; then
        body_md="📋 最近任务：${task}"
      else
        body_md="会话已结束"
      fi
      buttons="[$(_card_button "查看进度" "default" "进度")]"
      ;;
    *)
      header_color="blue"
      header_title="📢 [${project}]"
      body_md="$content"
      ;;
  esac

  local header
  header="$(_card_header "$header_color" "$header_title")"
  local fields
  fields="[{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**📁 项目**\n${project}\"}},{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**⏰ 时间**\n${time}\"}}]"
  local body
  body="$(_card_md "$body_md")"
  local actions
  actions="$(_card_actions "$buttons")"
  local note
  note='{"tag":"note","elements":[{"tag":"plain_text","content":"💡 点击按钮或回复文字指令：继续 | 进度 | 停下来 | 或输入具体需求"}]}'

  _build_card "$header" "$(_card_fields "$fields")" "$(_card_hr)" "$body" "$(_card_hr)" "$actions" "$note"
}

# Format a status reply as a Feishu interactive card
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
  local header_color="indigo"
  case "$status" in
    working) status_emoji="🔄"; header_color="turquoise" ;;
    waiting) status_emoji="⏸️"; header_color="orange" ;;
    error)   status_emoji="❌"; header_color="red" ;;
    idle)    status_emoji="💤"; header_color="grey" ;;
  esac

  local header
  header="$(_card_header "$header_color" "📊 [${sid}] 当前进度")"

  local fields
  fields="[{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**${status_emoji} 状态**\n${status}\"}},{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**📋 任务**\n${task}\"}}]"
  if [[ -n "$summary" ]]; then
    fields="[{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**${status_emoji} 状态**\n${status}\"}},{\"is_short\":true,\"text\":{\"tag\":\"lark_md\",\"content\":\"**📋 任务**\n${task}\"}},{\"is_short\":false,\"text\":{\"tag\":\"lark_md\",\"content\":\"**📝 最近操作**\n${summary}\"}}]"
  fi

  # Build todo elements
  local todo_elements="["
  local todo_count
  todo_count="$(jq ".sessions[\"$sid\"].todos | length" "$SESSIONS_FILE" 2>/dev/null || echo 0)"
  if [[ "$todo_count" -gt 0 ]]; then
    local todo_first=true
    while IFS= read -r todo_json; do
      local t_content t_status t_emoji
      t_content="$(echo "$todo_json" | jq -r '.content // ""')"
      t_status="$(echo "$todo_json" | jq -r '.status // "pending"')"
      case "$t_status" in
        completed)   t_emoji="✅" ;;
        in_progress) t_emoji="🔄" ;;
        *)           t_emoji="⏳" ;;
      esac
      if [[ "$todo_first" == "true" ]]; then
        todo_elements="${todo_elements}\"${t_emoji} ${t_content}\""
        todo_first=false
      else
        todo_elements="${todo_elements},\"${t_emoji} ${t_content}\""
      fi
    done < <(jq -c ".sessions[\"$sid\"].todos[]" "$SESSIONS_FILE" 2>/dev/null)
  fi
  todo_elements="${todo_elements}]"

  local todo_md=""
  if [[ "$todo_count" -gt 0 ]]; then
    # Join todo lines with newline
    todo_md="$(echo "$todo_elements" | jq -r '. | join("\n")')"
    todo_md="**📋 待办事项**\n${todo_md}"
  fi

  local actions
  actions="$(_card_actions "[$(_card_button "继续" "primary" "继续"),$(_card_button "暂停" "default" "停"),$(_card_button "刷新状态" "default" "进度")]")"

  local note
  note='{"tag":"note","elements":[{"tag":"plain_text","content":"⏰ 更新于：'"${last_update:-未知}"'"}]}'

  if [[ -n "$todo_md" ]]; then
    local todo_body
    todo_body="$(_card_md "$todo_md")"
    _build_card "$header" "$(_card_fields "$fields")" "$(_card_hr)" "$todo_body" "$(_card_hr)" "$actions" "$note"
  else
    _build_card "$header" "$(_card_fields "$fields")" "$(_card_hr)" "$actions" "$note"
  fi
}

# List all active sessions as a Feishu interactive card
list_active_sessions() {
  ensure_sessions_file
  local count
  count="$(jq '[.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped")] | length' "$SESSIONS_FILE" 2>/dev/null || echo 0)"

  if [[ "$count" -eq 0 ]]; then
    local header
    header="$(_card_header "grey" "💤 没有活跃会话")"
    local body
    body="$(_card_md "当前没有正在运行的 Claude Code 会话。")"
    _build_card "$header" "$body"
    return
  fi

  local header
  header="$(_card_header "indigo" "📊 活跃会话 (${count}个)")"

  local session_lines=""
  local idx=1
  while IFS= read -r entry; do
    local sid status task emoji
    sid="$(echo "$entry" | jq -r '.key')"
    status="$(echo "$entry" | jq -r '.value.status // "unknown"')"
    task="$(echo "$entry" | jq -r '.value.current_task // "无任务"')"
    case "$status" in
      working) emoji="🔄" ;;
      waiting) emoji="⏸️" ;;
      error)   emoji="❌" ;;
      *)       emoji="❓" ;;
    esac
    if [[ -n "$session_lines" ]]; then
      session_lines="${session_lines}\n"
    fi
    session_lines="${session_lines}${idx}. ${emoji} **[${sid}]** ${task}"
    idx=$((idx + 1))
  done < <(jq -c '.sessions | to_entries[] | select(.value.status != "idle" and .value.status != "stopped") | sort_by(.value.last_update)' "$SESSIONS_FILE" 2>/dev/null)

  local body
  body="$(_card_md "$session_lines")"

  local note
  note='{"tag":"note","elements":[{"tag":"plain_text","content":"💡 回复 \"1 继续\" 或 \"@项目名 进度\" 指定会话"}]}'

  _build_card "$header" "$body" "$note"
}
