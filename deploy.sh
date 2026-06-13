#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 3D Wall AI 一键部署脚本
# 用法: ./deploy.sh [--skip-check] [--no-build] [--skip-mirror] [--force]
# ═══════════════════════════════════════════════════════════════
set -e

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
SKIP_CHECK=false
NO_BUILD=false
SKIP_MIRROR=false
FORCE=false

for arg in "$@"; do
    case $arg in
        --skip-check)  SKIP_CHECK=true ;;
        --no-build)    NO_BUILD=true ;;
        --skip-mirror) SKIP_MIRROR=true ;;
        --force)       FORCE=true ;;
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

    # 镜像加速（国内/阿里云无 VPN 环境必备，否则拉 Docker Hub 镜像会超时失败）
    if [ "$(uname -s)" = "Linux" ]; then
        MIRRORS=$(docker info --format '{{range .RegistryMirrors}}{{.}} {{end}}' 2>/dev/null || true)
        if [ -z "${MIRRORS}" ]; then
            if [ "${SKIP_MIRROR}" = true ]; then
                echo "  ⚠️  未配置镜像加速（--skip-mirror），拉取 Docker Hub 镜像可能超时"
            elif [ -f ./scripts/setup-docker-mirror.sh ] && sudo -n true 2>/dev/null; then
                echo "  ⚙️  未配置镜像加速，自动配置多源加速（需重启 Docker）..."
                sudo ./scripts/setup-docker-mirror.sh
            else
                echo "❌ 未配置镜像加速，国内拉取 Docker Hub 镜像会超时失败"
                echo "   请先执行（阿里云强烈推荐用专属加速地址，最快最稳）:"
                echo "     阿里云控制台 → 容器镜像服务 → 镜像加速器，复制地址后:"
                echo "     sudo ./scripts/setup-docker-mirror.sh https://xxxx.mirror.aliyuncs.com"
                echo "   配置完成后重新运行 ./deploy.sh"
                echo "   或跳过本检查（不推荐）: ./deploy.sh --skip-mirror"
                exit 1
            fi
        else
            echo "  ✅ 镜像加速已配置"
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

    # 检查 pgdata 数据卷与当前 POSTGRES_PASSWORD 的一致性
    # 背景: POSTGRES_PASSWORD 只在【首次创建卷】时生效；事后改 .env 不会同步已有库，
    #       会导致 api 用新密码连旧卷 → "password authentication failed"。
    if [ "${FORCE}" = false ]; then
        echo "  🔐 检查 pgdata 数据卷密码一致性..."
        # 1) 定位 pgdata 卷真实名（compose 项目前缀 + pgdata）。优先从 db 容器挂载取，最准。
        PG_VOLUME=""
        DB_CID=$(docker compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)
        if [ -n "${DB_CID}" ]; then
            PG_VOLUME=$(docker inspect "${DB_CID}" \
                --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null || true)
        fi
        if [ -z "${PG_VOLUME}" ]; then
            # 兜底: 按卷名后缀查找
            PG_VOLUME=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E '_pgdata$' | head -1)
        fi

        if [ -n "${PG_VOLUME}" ]; then
            # 2) db 健康 → 用当前密码走 TCP（强制密码认证）试连
            DB_HEALTH=$(docker inspect "${DB_CID}" --format '{{.State.Health.Status}}' 2>/dev/null || echo "")
            if [ "${DB_HEALTH}" = "healthy" ]; then
                if docker compose -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="${POSTGRES_PASSWORD}" db \
                        psql -h localhost -U postgres -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
                    echo "     ✅ 密码一致（卷: ${PG_VOLUME}）"
                else
                    # 3) 不匹配 → 报错退出，给三种解决办法
                    echo "     ❌ 当前 .env 的 POSTGRES_PASSWORD 与已有数据卷中的密码不一致！"
                    echo "        POSTGRES_PASSWORD 仅在首次创建卷时生效，事后改 .env 不会同步已有库。"
                    echo ""
                    echo "        请选一种办法处理后重试："
                    echo "          1) 强制继续部署（可能连不上库）: ./deploy.sh --force"
                    echo "          2) 删除旧卷、重建空库（⚠️ 数据全丢）:"
                    echo "             docker compose -f ${COMPOSE_FILE} down -v"
                    echo "             （或仅删卷: docker volume rm ${PG_VOLUME}）"
                    echo "          3) 把 .env 的 POSTGRES_PASSWORD 改回【首次部署时】使用的旧密码"
                    exit 1
                fi
            else
                echo "     ⚠️  db 未健康（${DB_HEALTH:-未运行}），暂无法验证密码一致性（卷: ${PG_VOLUME}）"
                echo "        若你曾改过 POSTGRES_PASSWORD，启动后可能因旧卷密码不匹配而连不上库；"
                echo "        全新卷可忽略；旧卷改过密码请参照上面 3 种办法处理。"
            fi
        else
            echo "     ℹ️  未发现 pgdata 卷（首次部署），跳过"
        fi
    fi

    # 检查 LLM API Key
    if [ -z "${LLM_API_KEY:-}" ]; then
        echo "  ⚠️  LLM_API_KEY 未设置，将使用 mock 模式"
    fi

    echo ""
fi

# ─── Step 2: 构建镜像 ──────────────────────────────────────────────
if [ "${NO_BUILD}" = false ]; then
    echo "🔨 [2/5] 构建 Docker 镜像..."
    # 先预拉取基础镜像到本地：BuildKit 不一定读取 daemon.json 的 registry-mirrors，
    # 直接 build 可能绕过加速直连 Docker Hub 超时。预先 docker pull（走加速）让其
    # 命中本地缓存后，build 的 FROM 即不再触网。
    if [ -f ./scripts/pull-base-images.sh ]; then
        echo "  ⬇️  预拉取基础镜像..."
        ./scripts/pull-base-images.sh
    fi
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
