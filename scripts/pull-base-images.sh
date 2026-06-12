#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# 预拉取 Dockerfile 基础镜像
#
# 为什么需要: BuildKit（docker compose build 的默认构建器）不一定会读取
#   daemon.json 里的 registry-mirrors，可能绕过镜像加速直连 Docker Hub，
#   在国内/阿里云无 VPN 环境下会超时失败。
#   本脚本先用 `docker pull`（legacy 拉取会走已配置的镜像加速）把所有
#   Dockerfile 的 FROM 基础镜像拉到本地，之后 `docker compose build` 的
#   FROM 就直接命中本地缓存、不再触网，从而稳定通过。
#
# 自动从 apps/*/Dockerfile 解析所有 FROM 镜像（含多阶段、--platform），
#   无需手动维护清单。已在本地的镜像会跳过。
#
# 用法:
#   ./scripts/pull-base-images.sh                # 扫描 apps/api apps/web
#   ./scripts/pull-base-images.sh apps/x/Dockerfile apps/y/Dockerfile
# 适用: Linux / macOS 均可。
# ═══════════════════════════════════════════════════════════════
set -e

# 默认扫描的 Dockerfile（传入参数则覆盖）
if [ "$#" -gt 0 ]; then
    DOCKERFILES=("$@")
else
    DOCKERFILES=(apps/api/Dockerfile apps/web/Dockerfile)
fi

# 收集所有 FROM 镜像名：跳过 --platform=xxx，取随后第一个 token，忽略 AS 别名。
IMAGES="$(
    awk '
        /^[[:space:]]*FROM[[:space:]]/ {
            img = ""
            for (i = 2; i <= NF; i++) {
                if ($i ~ /^--platform=/) continue
                img = $i
                break
            }
            if (img != "" && img != "scratch") print img
        }
    ' "${DOCKERFILES[@]}" 2>/dev/null | sort -u
)"

if [ -z "${IMAGES}" ]; then
    echo "⚠️  未从 Dockerfile 解析到基础镜像，跳过预拉取"
    exit 0
fi

COUNT=$(printf '%s\n' "${IMAGES}" | grep -c .)
echo "⬇️  预拉取基础镜像（${COUNT} 个，走已配置的镜像加速）..."

FAILED=0
while IFS= read -r img; do
    [ -z "${img}" ] && continue
    if docker image inspect "${img}" >/dev/null 2>&1; then
        echo "   ✅ ${img}（本地已存在，跳过）"
        continue
    fi
    echo "   ⬇️  ${img} ..."
    if ! docker pull "${img}"; then
        echo "   ❌ 拉取 ${img} 失败"
        FAILED=$((FAILED + 1))
    fi
done < <(printf '%s\n' "${IMAGES}")

if [ "${FAILED}" -ne 0 ]; then
    echo ""
    echo "❌ ${FAILED} 个基础镜像拉取失败"
    echo "   请先配置镜像加速: sudo ./scripts/setup-docker-mirror.sh"
    echo "   （阿里云推荐用专属地址: 阿里云控制台 → 容器镜像服务 → 镜像加速器）"
    exit 1
fi

echo "✅ 基础镜像就绪，可以开始 docker compose build"
