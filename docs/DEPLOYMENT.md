# 3D Wall AI 生产部署指南

## 1. 前置条件

| 项目 | 最低要求 |
|------|---------|
| 操作系统 | Ubuntu 22.04+ / Debian 12+ / CentOS 8+ |
| Docker | 24.0+ |
| Docker Compose | v2.0+ |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | 40GB+（SSD 推荐） |
| CPU | 2 核+ |
| 端口 | 3000（前端）、8000（API）开放 |

### 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 重新登录终端生效
```

## 2. 快速部署（3 步）

### Step 1: 获取代码

```bash
git clone https://github.com/puppyfront-web/3D.git
cd 3D
```

### Step 2: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
nano .env
```

**必须修改的变量：**

```bash
# 生成安全密码（执行后复制结果到 .env）
openssl rand -hex 32

# ─── 必填项 ───
POSTGRES_PASSWORD=<粘贴生成的密码>
API_KEY=<粘贴生成的密码>
SECRET_KEY=<粘贴生成的密码>

# ─── AI Provider 配置 ───
LLM_PROVIDER=openai
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://your-provider.com/v1
LLM_MODEL=gpt-4o

EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://your-provider.com/v1
EMBEDDING_MODEL=text-embedding-3-small

IMAGE_PROVIDER=openai
IMAGE_API_KEY=sk-xxx
IMAGE_BASE_URL=https://your-provider.com/v1
IMAGE_MODEL=gpt-image-2

# ─── 前端 API 地址（重点！详见第 4 节「同源 /api 设计」）───
# ① 只填域名根，【不带 /api】（接口路径已自带 /api/v1，加了会变成 /api/api/v1）
# ② 协议要和站点一致：站点 http 就填 http://，加了 SSL 再换 https://
# ③ 这是【构建时】注入值——改完必须重建 web 镜像，否则不生效（见第 4 节）
NEXT_PUBLIC_API_URL=https://yourdomain.com
# 走同域 /api 反代时请求是同源、CORS 不会触发；这里仍填上以备直连/开发场景
CORS_ORIGINS=https://yourdomain.com
```

### Step 3: 一键部署

```bash
chmod +x deploy.sh
./deploy.sh
```

## 3. 手动部署

如果不使用一键脚本：

```bash
# 构建并启动
docker compose -f docker-compose.prod.yml up -d --build

# 查看状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f api
```

## 4. 反向代理配置

### 宝塔面板

1. 添加网站，绑定域名，申请 SSL
2. 设置反向代理：

**前端代理（默认）：**

| 配置项 | 值 |
|--------|-----|
| 目标 URL | `http://127.0.0.1:3000` |
| 发送域名 | `$host` |

**API 代理（添加路径 `/api`）：**

| 配置项 | 值 |
|--------|-----|
| 路径 | `/api` |
| 目标 URL | `http://127.0.0.1:8000` |
| 发送域名 | `$host` |

### 1Panel / Nginx 手动配置

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # 文件上传大小限制（文档/PPT 上传）
    client_max_body_size 100M;

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式响应支持（对话功能需要）
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # API 文档
    location /docs {
        proxy_pass http://127.0.0.1:8000;
    }
    location /openapi.json {
        proxy_pass http://127.0.0.1:8000;
    }

    # API 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000;
    }

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### 同源 /api 设计（关键概念，部署前必读）

前端访问后端走的是 **同域 `/api` 反向代理**（nginx 把 `/api/*` 转给 api 容器），不是浏览器直连 8000 端口。理解以下几点可避免 90% 的「前端连不上后端 / CORS 报错」。

**请求链路：**

```
浏览器页面:   https://yourdomain.com              ← nginx location / → web:3000
前端发请求:   https://yourdomain.com/api/v1/...   ← NEXT_PUBLIC_API_URL(域名根) + 接口路径(自带 /api/v1)
nginx 转发:   location /api/ → proxy_pass http://127.0.0.1:8000   （保留 /api 前缀，不要 rewrite 掉）
FastAPI:      路由统一挂在 /api/v1 下 → 命中 ✅
```

因为页面和 API **同域**，浏览器视为同源请求，**CORS 根本不会触发**——这也是 `CORS_ORIGINS` 在同源部署下其实用不上的原因（它只是给直连/本地开发兜底）。

**`NEXT_PUBLIC_API_URL` 的三个关键认知：**

| # | 认知 | 说明 |
|---|------|------|
| ① | **不带 `/api`** | 接口路径已自带 `/api/v1`，base 只填域名根；填了 `/api` 会变成 `/api/api/v1` |
| ② | **协议与页面一致** | 页面是 `http://` 就填 `http://yourdomain.com`；加了 SSL 再换 `https://`。不一致会触发混合内容拦截或直接连不上 |
| ③ | **构建时注入** | `NEXT_PUBLIC_*` 在 `next build` 时被写死进 JS bundle。**改 `.env` 后必须重建 web 镜像**，否则浏览器还在跑带旧地址的 bundle |

**`.env` 会覆盖 compose 默认值（最隐蔽的坑）：**

`docker compose` 启动时会自动读取项目根目录的 `.env`，其中同名变量会 **覆盖** `docker-compose.prod.yml` 里的 `${VAR:-默认}`。所以仓库里改了默认域名 **不够**——服务器上已存在的 `.env` 才是真正生效点。升级时若改了默认域名，务必同步改服务器 `.env`。

**改了 `NEXT_PUBLIC_API_URL` 后必须重建（最高频踩坑）：**

```bash
# ❌ 只 up -d：复用旧镜像，bundle 不变，等于没改
docker compose -f docker-compose.prod.yml up -d

# ✅ 带 --build 重建 web 镜像（或直接 ./deploy.sh）
docker compose -f docker-compose.prod.yml up -d --build web
```

**验证 bundle 已更新：** 浏览器硬刷新（Ctrl/Cmd+Shift+R，绕过旧 bundle 缓存）→ Network 面板里请求应指向 `https://yourdomain.com/api/v1/...`，**不再是 `localhost:8000`**。若仍是 localhost，说明镜像没重建或 `.env` 没改。

**加 SSL 时：** 站点从 `http://` 切到 `https://` 后，把 `.env` 里 `NEXT_PUBLIC_API_URL` 的协议同步改成 `https://`，再重建一次 web 镜像。

## 5. 验证清单

部署完成后逐项检查：

```bash
# 1. 所有容器运行中且健康
docker compose -f docker-compose.prod.yml ps
# 期望: 3 个服务状态为 healthy

# 2. API 健康检查
curl http://localhost:8000/health
# 期望: {"status":"healthy",...}

# 3. 前端可访问
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
# 期望: 200

# 4. 数据库连接正常（检查 API 日志）
docker compose -f docker-compose.prod.yml logs api | grep -i "migrations complete"
# 期望: 看到 "Migrations complete."

# 5. 存储目录可写
docker compose -f docker-compose.prod.yml exec api ls -la /app/storage/
# 期望: 目录存在且可访问

# 6. 访问前端页面，创建项目测试完整流程
```

## 6. 备份与恢复

### 备份

```bash
./scripts/backup.sh
# 备份保存到 ./backups/3dwall_YYYYMMDD_HHMMSS/
```

### 恢复

```bash
./scripts/restore.sh ./backups/3dwall_20260610_153000
```

### 定时备份（crontab）

```bash
# 每天凌晨 3 点自动备份，保留 7 天
crontab -e
# 添加:
0 3 * * * cd /path/to/3D && ./scripts/backup.sh >> /var/log/3dwall-backup.log 2>&1 && find ./backups -mtime +7 -type d -exec rm -rf {} +
```

## 7. 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重新部署
./deploy.sh
```

## 8. 常用运维命令

```bash
# 查看服务状态
docker compose -f docker-compose.prod.yml ps

# 查看实时日志
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f web

# 重启单个服务
docker compose -f docker-compose.prod.yml restart api

# 进入容器调试
docker compose -f docker-compose.prod.yml exec api bash
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d 3dwall

# 清理旧镜像
docker image prune -f

# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 停止并清除数据（危险！）
docker compose -f docker-compose.prod.yml down -v
```

## 9. 常见问题

### Q: API 启动报 "Database not ready"

数据库还在初始化，等待片刻自动重试。如果持续失败：
```bash
# 检查数据库状态
docker compose -f docker-compose.prod.yml logs db
# 手动测试连接
docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres
```

### Q: 前端页面空白 / API 连接失败 / Network 面板里请求打到 `localhost:8000`

**典型症状：** 浏览器 Console 报 `Access to fetch at 'http://localhost:8000/api/v1/...' has been blocked by CORS`，或 `net::ERR_FAILED`。这说明 **web 镜像的 JS bundle 里还固化着 `localhost:8000`**——`.env` 没改、或改了但没重建镜像。

详见第 4 节「同源 /api 设计」。修复：
```bash
# 1. 改 .env：协议要和站点一致（站点 http 就填 http://yourdomain.com），不带 /api
#    NEXT_PUBLIC_API_URL=https://yourdomain.com
nano .env

# 2. 必须带 --build 重建 web 镜像（只 up -d 无效，bundle 不变）
docker compose -f docker-compose.prod.yml up -d --build web

# 3. 浏览器硬刷新（Ctrl/Cmd+Shift+R）→ Network 面板确认请求指向 yourdomain.com
```

### Q: CORS 报错

**先确认请求地址对不对：** 走同域 `/api` 反代时，浏览器看到的请求是 `https://yourdomain.com/api/v1/...`，与页面同源，**CORS 本不该触发**。如果 Console 里的请求是 `http://localhost:8000/...`，那不是 CORS 配置问题——是 bundle 没重建，按上一条「前端页面空白 / API 连接失败」处理。

只有在 **直连后端端口**（如开发场景 `http://localhost:8000`）时才需要 CORS 白名单，此时在 `.env` 把前端域名加进去：
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Q: 文件上传失败

```bash
# 检查存储卷
docker compose -f docker-compose.prod.yml exec api ls -la /app/storage/
# 检查 Nginx 上传大小限制（需 >= 100M）
```

### Q: LLM 调用超时

检查 API 网络连通性：
```bash
docker compose -f docker-compose.prod.yml exec api \
    curl -s -w "%{http_code}" https://your-llm-provider.com/v1/models \
    -H "Authorization: Bearer $LLM_API_KEY"
```
