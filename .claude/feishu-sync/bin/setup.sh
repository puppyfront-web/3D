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

# Initialize sessions registry
cat > "$STATE_DIR/sessions.json" <<'EOF'
{"sessions":{},"last_polled_msg_ts":"0"}
EOF

echo ""
echo "✅ 配置完成！"
echo "   config.json: $CONFIG_FILE"
echo "   sessions.json: $STATE_DIR/sessions.json"
echo ""
echo "发送测试消息..."
TEST_MSG=$'🤖 Claude Code 飞书同步插件已连接\n\n后续你可以在这里查看工作状态并发送远程指令。'
lark-cli im +messages-send --chat-id "$CHAT_ID" --text "$TEST_MSG" --as bot

echo ""
echo "✅ 测试消息已发送！请检查飞书群。"
echo ""
echo "下一步：配置 Claude Code hooks（见 Task 5）"
