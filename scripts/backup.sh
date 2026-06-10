#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 3D Wall AI 数据备份脚本
# 用法: ./scripts/backup.sh [备份目录]
# ═══════════════════════════════════════════════════════════════
set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${1:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/3dwall_${TIMESTAMP}"

echo "══════════════════════════════════════════"
echo "  3D Wall AI 备份工具"
echo "══════════════════════════════════════════"

# 创建备份目录
mkdir -p "${BACKUP_PATH}"

# 1. 备份数据库
echo "[1/3] 备份数据库..."
docker compose -f "${COMPOSE_FILE}" exec -T db \
    pg_dump -U postgres -d 3dwall -Fc --compress=9 \
    > "${BACKUP_PATH}/database.dump"
echo "  ✅ 数据库备份完成: $(du -h "${BACKUP_PATH}/database.dump" | cut -f1)"

# 2. 备份文件存储
echo "[2/3] 备份文件存储..."
docker compose -f "${COMPOSE_FILE}" exec -T api \
    tar czf - -C /app storage \
    > "${BACKUP_PATH}/storage.tar.gz" 2>/dev/null || {
    echo "  ⚠️  文件存储为空或不可访问，跳过"
    touch "${BACKUP_PATH}/storage.tar.gz"
}
echo "  ✅ 文件存储备份完成: $(du -h "${BACKUP_PATH}/storage.tar.gz" | cut -f1)"

# 3. 保存环境配置
echo "[3/3] 保存配置快照..."
if [ -f .env ]; then
    cp .env "${BACKUP_PATH}/.env.snapshot"
    echo "  ✅ .env 已保存"
else
    echo "  ⚠️  未找到 .env 文件"
fi

# 输出摘要
TOTAL_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
echo ""
echo "══════════════════════════════════════════"
echo "  备份完成！"
echo "  路径: ${BACKUP_PATH}"
echo "  大小: ${TOTAL_SIZE}"
echo "  时间: ${TIMESTAMP}"
echo "══════════════════════════════════════════"
