# 售前方案工作台 — 客户私有化安装指南

> 目标：**30 分钟内** 完成一套可演示环境（Docker Compose）。

## 1. 环境要求

| 项 | 要求 |
|----|------|
| 系统 | Linux（推荐 Ubuntu 22.04+）或 macOS（开发演示） |
| Docker | 24+ |
| Docker Compose | v2+ |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | 40GB+ |
| 端口 | 3000（前端）、8000（API）；生产可经 Nginx 反代 |

## 2. 快速安装（开发 / POC）

```bash
git clone <your-repo-url> presale-workspace
cd presale-workspace

# 启动（默认 Mock LLM，无需 API Key）
docker compose up -d --build

# 查看状态
docker compose ps
curl -sf http://localhost:8000/health
```

访问：

- 前端：http://localhost:3000（若端口被占用，在 `.env` 设置 `WEB_PORT=3001` 后重启）  
- API 文档：http://localhost:8000/docs  

默认账号（**首次登录后请修改密码**）：

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | admin@3dwall.com | admin123 |
| 演示用户 | demo@3dwall.com | demo123 |

## 3. 生产安装

```bash
cp .env.example .env
# 编辑 .env：POSTGRES_PASSWORD、SECRET_KEY、API_KEY（openssl rand -hex 32）

./deploy.sh
# 或：docker compose -f docker-compose.prod.yml up -d --build
```

详见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

## 4. 配置真实 LLM（可选）

在 `.env` 或 compose 环境变量中：

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key
LLM_BASE_URL=          # OpenAI 兼容网关地址，可选
LLM_MODEL=gpt-4o

EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-key
EMBEDDING_MODEL=text-embedding-3-small
```

修改后重启 API：

```bash
docker compose restart api
```

## 5. 演示数据

API 启动时会自动执行（幂等）：

- `default_presale_sop` — 导出门控所需默认 SOP  
- 3 条演示案例 — 标签 `presale_demo_seed`，可在 `/admin/cases` 查看  

## 6. 验收检查清单

- [ ] `curl http://localhost:8000/health` 返回 healthy  
- [ ] 可登录 `/login`  
- [ ] 可创建项目并进入 Canvas  
- [ ] 按 [DEMO.md](./DEMO.md) 走完 10 步  

## 7. 备份（生产）

```bash
./scripts/backup.sh
```

## 8. 故障排查

| 问题 | 排查 |
|------|------|
| API 启动失败 | `docker compose logs api`，检查迁移是否到 head |
| 前端无法调 API | 检查 `NEXT_PUBLIC_API_URL`、CORS、浏览器 Network |
| 3000 端口占用 | 改 web 端口映射或释放占用进程 |

技术支持：部署问题请附带 `docker compose logs api` 末 50 行。
