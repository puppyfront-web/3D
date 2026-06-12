#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 3D Wall AI 一键部署脚本
# 用法: ./deploy.sh [--skip-check] [--no-build]
# ═══════════════════════════════════════════════════════════════
set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
SKIP_CHECK=false
NO_BUILD=false

for arg in "$@"; do
    case $arg in
        --skip-check) SKIP_CHECK=true ;;
        --no-build)   NO_BUILD=true ;;
    esac
done

echo "══════════════════════════════════════════"
echo "  3D Wall AI 部署工具"
echo "  Compose: ${COMPOSE_FILE}"
echo "══════════════════════════════════════════"
echo ""

# ─── Step 1: 前置检查 ──────────────────────────────────────────────
if [ "${SKIP_CHECK}" = false ]; then
    echo "🔍 [1/5] 前置检查..."

    # 检查 Docker
    if ! command -v docker &>/dev/null; then
        echo "❌ Docker 未安装"
        exit 1
    fi
    echo "  ✅ Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"

    # 检查 Docker Compose
    if ! docker compose version &>/dev/null; then
        echo "❌ Docker Compose v2 未安装"
        exit 1
    fi
    echo "  ✅ Docker Compose: $(docker compose version --short)"

    # 检查镜像加速（仅 Linux 服务器，国内拉取 Docker Hub 镜像更快）
    if [ "$(uname -s)" = "Linux" ]; then
        MIRRORS=$(docker info --format '{{range .RegistryMirrors}}{{.}} {{end}}' 2>/dev/null || true)
        if [ -z "${MIRRORS}" ]; then
            echo "  💡 未配置镜像加速，国内拉取镜像可能较慢"
            echo "     一键配置（阿里云）: sudo ./scripts/setup-docker-mirror.sh"
        fi
    fi

    # 检查 .env 文件
    if [ ! -f .env ]; then
        echo "❌ 未找到 .env 文件"
        echo "   请执行: cp .env.example .env && 编辑 .env 填写配置"
        exit 1
    fi
    echo "  ✅ .env 文件存在"

    # 检查必需变量
    source .env
    for VAR in POSTGRES_PASSWORD SECRET_KEY; do
        VAL=$(eval echo "\${${VAR}:-}")
        if [ -z "${VAL}" ]; then
            echo "❌ .env 缺少必需变量: ${VAR}"
            echo "   生成方式: openssl rand -hex 32"
            exit 1
        fi
    done
    if [ "${POSTGRES_PASSWORD}" = "postgres" ] || [ "${POSTGRES_PASSWORD}" = "change-this-in-production" ]; then
        echo "❌ POSTGRES_PASSWORD 仍为默认值，请修改！"
        exit 1
    fi
    echo "  ✅ 必需变量已配置"

    # 检查 LLM API Key
    if [ -z "${LLM_API_KEY:-}" ]; then
        echo "  ⚠️  LLM_API_KEY 未设置，将使用 mock 模式"
    fi

    echo ""
fi

# ─── Step 2: 构建镜像 ──────────────────────────────────────────────
if [ "${NO_BUILD}" = false ]; then
    echo "🔨 [2/5] 构建 Docker 镜像..."
    docker compose -f "${COMPOSE_FILE}" build --parallel 2>&1 | tail -5
    echo "  ✅ 镜像构建完成"
    echo ""
else
    echo "⏩ [2/5] 跳过构建 (--no-build)"
    echo ""
fi

# ─── Step 3: 启动服务 ──────────────────────────────────────────────
echo "🚀 [3/5] 启动服务..."
docker compose -f "${COMPOSE_FILE}" up -d
echo "  ✅ 服务已启动"
echo ""

# ─── Step 4: 健康检查 ──────────────────────────────────────────────
echo "🏥 [4/5] 等待服务健康..."
MAX_WAIT=120
WAITED=0
while true; do
    STATUS=$(docker compose -f "${COMPOSE_FILE}" ps --format json 2>/dev/null | \
        python3 -c "
import sys, json
healthy = 0
total = 0
for line in sys.stdin:
    try:
        s = json.loads(line)
        health = s.get('Health', s.get('health', ''))
        total += 1
        if health == 'healthy':
            healthy += 1
    except: pass
print(f'{healthy}/{total}')
" 2>/dev/null || echo "0/0")

    if echo "${STATUS}" | grep -qv "0/"; then
        echo "  ✅ 服务健康: ${STATUS}"
        break
    fi

    WAITED=$((WAITED + 5))
    if [ "${WAITED}" -ge "${MAX_WAIT}" ]; then
        echo "  ⚠️  超时 (${MAX_WAIT}s)，当前状态: ${STATUS}"
        echo "  查看日志: docker compose -f ${COMPOSE_FILE} logs"
        break
    fi
    sleep 5
done
echo ""

# ─── Step 5: 输出摘要 ──────────────────────────────────────────────
source .env 2>/dev/null || true
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"

echo "══════════════════════════════════════════"
echo "  🎉 部署完成！"
echo ""
echo "  前端: http://localhost:${WEB_PORT}"
echo "  API:  http://localhost:${API_PORT}"
echo "  健康: http://localhost:${API_PORT}/health"
echo ""
echo "  常用命令:"
echo "  查看状态: docker compose -f ${COMPOSE_FILE} ps"
echo "  查看日志: docker compose -f ${COMPOSE_FILE} logs -f api"
echo "  停止服务: docker compose -f ${COMPOSE_FILE} down"
echo "  备份数据: ./scripts/backup.sh"
echo "══════════════════════════════════════════"
