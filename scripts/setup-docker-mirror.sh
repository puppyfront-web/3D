#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 3D Wall AI Docker 镜像加速一键配置
# 用途: 配置阿里云镜像加速，加快国内服务器拉取 Docker Hub 镜像
# 用法:
#   ./scripts/setup-docker-mirror.sh                          # 用默认加速地址
#   ./scripts/setup-docker-mirror.sh https://xxxx.mirror.aliyuncs.com
#   DOCKER_MIRROR=https://xxxx.mirror.aliyuncs.com ./scripts/setup-docker-mirror.sh
# 适用: Linux 服务器（macOS 请在 Docker Desktop 设置中配置）
# ═══════════════════════════════════════════════════════════════
set -e

# 默认阿里云个人加速地址（可通过参数或 DOCKER_MIRROR 环境变量覆盖）
MIRROR="${1:-${DOCKER_MIRROR:-https://oj569bok.mirror.aliyuncs.com}}"
DAEMON_JSON="/etc/docker/daemon.json"

echo "══════════════════════════════════════════"
echo "  Docker 镜像加速配置"
echo "  Mirror: ${MIRROR}"
echo "══════════════════════════════════════════"

# ─── 平台检查 ──────────────────────────────────────────────────
OS_TYPE="$(uname -s)"
if [ "${OS_TYPE}" != "Linux" ]; then
    echo ""
    echo "⚠️  当前系统: ${OS_TYPE}"
    echo "   本脚本仅适用于 Linux 服务器。"
    echo ""
    if [ "${OS_TYPE}" = "Darwin" ]; then
        echo "   macOS Docker Desktop 配置方式："
        echo "     1) 打开 Docker Desktop → Settings → Docker Engine"
        echo "     2) 在 JSON 中加入（与现有字段合并）："
        echo '        "registry-mirrors": ["'"${MIRROR}"'"]'
        echo "     3) 点击 Apply & Restart"
        echo ""
        echo "   或直接编辑 ~/.docker/daemon.json 后重启 Docker Desktop。"
    fi
    exit 0
fi

# ─── 权限检查 ──────────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo "❌ 需要 root 权限来写入 ${DAEMON_JSON}"
    echo "   请用 sudo 运行: sudo $0 $*"
    exit 1
fi

# ─── 依赖检查（python3 用于安全合并 JSON）──────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，无法安全合并 ${DAEMON_JSON}"
    echo "   请先安装: sudo apt-get install -y python3"
    exit 1
fi

# ─── 读取并合并 daemon.json ────────────────────────────────────
# 幂等：已包含该加速地址则不重复添加、不重启
EXISTING=$(sudo cat "${DAEMON_JSON}" 2>/dev/null || echo "{}")
TMP_OUT="$(mktemp)"
trap 'rm -f "${TMP_OUT}"' EXIT

CHANGED=$(printf '%s' "${EXISTING}" | MIRROR="${MIRROR}" python3 - "${TMP_OUT}" <<'PY'
import json, os, sys
mirror = os.environ["MIRROR"]
out_path = sys.argv[1]
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    data = {}
mirrors = data.get("registry-mirrors", [])
if mirror in mirrors:
    json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    print(0)
else:
    # 新加速地址置顶，保留其余已有镜像
    mirrors.insert(0, mirror)
    data["registry-mirrors"] = mirrors
    json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    print(1)
PY
)

# ─── 应用变更 ──────────────────────────────────────────────────
case "${CHANGED}" in
    0|1) ;;
    *) echo "❌ 合并 ${DAEMON_JSON} 失败（CHANGED='${CHANGED}'），已中止，未改动 Docker 配置"; exit 1 ;;
esac
if [ "${CHANGED}" = "0" ]; then
    echo "✅ 镜像加速已配置，无需重复操作: ${MIRROR}"
    rm -f "${TMP_OUT}"
else
    echo "📝 写入 ${DAEMON_JSON} ..."
    sudo mkdir -p /etc/docker
    sudo cp "${TMP_OUT}" "${DAEMON_JSON}"
    sudo chown root:root "${DAEMON_JSON}"
    sudo chmod 644 "${DAEMON_JSON}"
    rm -f "${TMP_OUT}"

    echo "🔄 重新加载并重启 Docker ..."
    if command -v systemctl &>/dev/null; then
        sudo systemctl daemon-reload
        sudo systemctl restart docker
    else
        sudo service docker restart
    fi
    echo "✅ 已配置并重启 Docker: ${MIRROR}"
fi

# ─── 验证 ──────────────────────────────────────────────────────
echo ""
echo "📋 当前 Docker Registry Mirrors:"
docker info 2>/dev/null | grep -A3 "Registry Mirrors" || echo "   （等待 Docker 完全就绪后可用 docker info 查看）"
echo ""
echo "💡 测试拉取速度: docker pull node:20-alpine"
echo "══════════════════════════════════════════"
