#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Docker 镜像加速一键配置（多源容灾）
#
# 用途: 给 Linux 服务器（尤其是阿里云 ECS 等国内无 VPN 环境）配置一组
#       Docker Hub 镜像加速源，保证 docker pull / build 能可靠拉到镜像。
#
# 为什么是「多个源」: 单一加速源随时可能失效（被限流/下线），配置一组
#       Docker 会按顺序逐个尝试，任意一个可用即可拉取，容灾性最高。
#
# 用法:
#   sudo ./scripts/setup-docker-mirror.sh                          # 用默认公共源列表
#   sudo ./scripts/setup-docker-mirror.sh https://xxxx.mirror.aliyuncs.com
#   DOCKER_MIRRORS="https://a https://b" sudo ./scripts/setup-docker-mirror.sh
#
# 🟢 阿里云 ECS 强烈建议: 用你自己的专属加速地址（速度最快、最稳定）:
#       阿里云控制台 → 容器镜像服务 ACR → 镜像加速器，复制形如
#       https://xxxx.mirror.aliyuncs.com 的地址作为第一个参数传入。
#
# 适用: Linux 服务器（macOS 请在 Docker Desktop → Settings → Docker Engine 配置）
# 幂等: 已配置的源不会重复添加；无变更时不重启 Docker。
# ═══════════════════════════════════════════════════════════════
set -e

# 默认公共加速源（按优先级；均为当前可用的公共源，实测可达）。
# 注意: 公共源不保证长期可用，生产环境请优先使用你自己的阿里云专属地址。
DEFAULT_MIRRORS=(
    "https://docker.m.daocloud.io"
    "https://docker.1ms.run"
    "https://docker.xuanyuan.me"
)

# 解析要写入的源列表：参数 > DOCKER_MIRRORS(空格分隔) > DOCKER_MIRROR(旧单值) > 默认
if [ -n "${1:-}" ]; then
    NEW_MIRRORS=("$1")
elif [ -n "${DOCKER_MIRRORS:-}" ]; then
    read -ra NEW_MIRRORS <<< "${DOCKER_MIRRORS}"
elif [ -n "${DOCKER_MIRROR:-}" ]; then
    NEW_MIRRORS=("${DOCKER_MIRROR}")
else
    NEW_MIRRORS=("${DEFAULT_MIRRORS[@]}")
fi

DAEMON_JSON="/etc/docker/daemon.json"

echo "══════════════════════════════════════════"
echo "  Docker 镜像加速配置（多源容灾）"
printf "  镜像源:\n"
for m in "${NEW_MIRRORS[@]}"; do printf "    - %s\n" "$m"; done
echo "══════════════════════════════════════════"

# ─── 平台检查 ──────────────────────────────────────────────────
OS_TYPE="$(uname -s)"
if [ "${OS_TYPE}" != "Linux" ]; then
    echo ""
    echo "⚠️  当前系统: ${OS_TYPE}，本脚本仅适用于 Linux 服务器。"
    if [ "${OS_TYPE}" = "Darwin" ]; then
        echo "   macOS Docker Desktop 配置方式："
        echo "     1) 打开 Docker Desktop → Settings → Docker Engine"
        echo "     2) 在 JSON 中加入（与现有字段合并）："
        printf '        "registry-mirrors": [\n'
        for m in "${NEW_MIRRORS[@]}"; do printf '          "%s"\n' "$m"; done
        echo "        ]"
        echo "     3) 点击 Apply & Restart"
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
    echo "   请先安装: sudo apt-get install -y python3   (或 yum install -y python3)"
    exit 1
fi

# ─── 读取并合并 daemon.json ────────────────────────────────────
EXISTING=$(sudo cat "${DAEMON_JSON}" 2>/dev/null || echo "{}")
TMP_OUT="$(mktemp)"
trap 'rm -f "${TMP_OUT}"' EXIT

# 把列表拼成空格分隔串传给 python
NEW_MIRRORS_STR="${NEW_MIRRORS[*]}"
CHANGED=$(printf '%s' "${EXISTING}" | NEW_MIRRORS="${NEW_MIRRORS_STR}" python3 - "${TMP_OUT}" <<'PY'
import json, os, sys
new_mirrors = os.environ["NEW_MIRRORS"].split()
out_path = sys.argv[1]
try:
    data = json.loads(sys.stdin.read() or "{}")
except Exception:
    data = {}
existing = data.get("registry-mirrors", [])
# 仅追加尚未存在的源；新源置顶，保留已有源作为兜底。
added = [m for m in new_mirrors if m not in existing]
if added:
    data["registry-mirrors"] = added + existing
    json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    print(1)
else:
    json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    print(0)
PY
)

case "${CHANGED}" in
    0|1) ;;
    *) echo "❌ 合并 ${DAEMON_JSON} 失败（CHANGED='${CHANGED}'），已中止，未改动 Docker 配置"; exit 1 ;;
esac

if [ "${CHANGED}" = "0" ]; then
    echo "✅ 镜像加速已全部配置，无需重复操作"
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
    # 重启后 daemon 需要片刻就绪
    sleep 2
    echo "✅ 已配置并重启 Docker"
fi

# ─── 验证 ──────────────────────────────────────────────────────
echo ""
echo "📋 当前 Docker Registry Mirrors:"
docker info 2>/dev/null | grep -A6 "Registry Mirrors" || echo "   （等待 Docker 完全就绪后可用 docker info 查看）"
echo ""
echo "💡 测试拉取: docker pull node:20-alpine"
echo "══════════════════════════════════════════"
