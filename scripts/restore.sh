#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 3D Wall AI 数据恢复脚本
# 用法: ./scripts/restore.sh <备份目录>
# 示例: ./scripts/restore.sh ./backups/3dwall_20260610_153000
# ═══════════════════════════════════════════════════════════════
set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_PATH="${1:?用法: ./scripts/restore.sh <备份目录>}"

# 验证备份文件
if [ ! -d "${BACKUP_PATH}" ]; then
    echo "❌ 备份目录不存在: ${BACKUP_PATH}"
    exit 1
fi

if [ ! -f "${BACKUP_PATH}/database.dump" ]; then
    echo "❌ 未找到数据库备份: ${BACKUP_PATH}/database.dump"
    exit 1
fi

echo "══════════════════════════════════════════"
echo "  3D Wall AI 数据恢复"
echo "  备份: ${BACKUP_PATH}"
echo "══════════════════════════════════════════"
echo ""
echo "⚠️  此操作将覆盖当前数据！"
read -p "确认继续？(输入 YES): " CONFIRM
if [ "${CONFIRM}" != "YES" ]; then
    echo "已取消"
    exit 0
fi

# 1. 停止 API 和 Web 服务
echo ""
echo "[1/4] 停止 API 和 Web 服务..."
docker compose -f "${COMPOSE_FILE}" stop api web

# 2. 恢复数据库
echo "[2/4] 恢复数据库..."
# 先清除现有数据
docker compose -f "${COMPOSE_FILE}" exec -T db \
    psql -U postgres -d 3dwall -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
# 恢复备份
docker compose -f "${COMPOSE_FILE}" exec -T db \
    pg_restore -U postgres -d 3dwall --no-owner --no-privileges \
    < "${BACKUP_PATH}/database.dump" || {
    echo "⚠️  pg_restore 有警告，继续..."
}
# 确保 vector 扩展存在
docker compose -f "${COMPOSE_FILE}" exec -T db \
    psql -U postgres -d 3dwall -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true
echo "  ✅ 数据库恢复完成"

# 3. 恢复文件存储
echo "[3/4] 恢复文件存储..."
if [ -f "${BACKUP_PATH}/storage.tar.gz" ] && [ -s "${BACKUP_PATH}/storage.tar.gz" ]; then
    docker compose -f "${COMPOSE_FILE}" exec -T api \
        tar xzf - -C /app \
        < "${BACKUP_PATH}/storage.tar.gz"
    echo "  ✅ 文件存储恢复完成"
else
    echo "  ⚠️  无文件存储备份，跳过"
fi

# 4. 重启服务
echo "[4/4] 重启服务..."
docker compose -f "${COMPOSE_FILE}" start api web

echo ""
echo "══════════════════════════════════════════"
echo "  恢复完成！等待服务健康..."
echo "══════════════════════════════════════════"

# 等待健康检查
sleep 10
docker compose -f "${COMPOSE_FILE}" ps
