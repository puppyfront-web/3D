# 3D 展示幕墙 AI 专家系统

面向 3D 展示幕墙、裸眼 3D、LED 媒体立面、数字视觉展示行业的 AI Native 专家系统。

## 产品形态

- **内部 AI 工作台** — 项目驱动的方案生成工作流
- **专家能力管理后台** — SOP、Prompt、模板、案例的可配置管理
- **RAG 知识库** — 企业知识的可追溯检索
- **Agent 工作流** — 企业解析、策划案生成、视觉创意

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + TypeScript + TailwindCSS + shadcn/ui |
| 后端 | FastAPI + SQLAlchemy + Pydantic |
| 数据库 | PostgreSQL + pgvector |
| AI | OpenAI-compatible LLM/Embedding/Image（含 Mock） |

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.11+
- PostgreSQL 16 + pgvector
- Docker & Docker Compose（可选）

### 使用 Docker Compose

```bash
# 启动所有服务
docker compose up -d

# 访问
# 前端：http://localhost:3000
# 后端 API：http://localhost:8000
# API 文档：http://localhost:8000/docs
```

### 生产部署（国内服务器）

```bash
# 1. 配置环境变量（POSTGRES_PASSWORD / SECRET_KEY / API_KEY 用 openssl rand -hex 32 生成）
cp .env.example .env

# 2.（可选但推荐）配置阿里云镜像加速，加快拉取 Docker Hub 镜像
sudo ./scripts/setup-docker-mirror.sh

# 3. 一键部署（含前置检查、构建、健康检查）
./deploy.sh
```

部署后访问前端 `http://<服务器IP>:3000`、API `http://<服务器IP>:8000`。
常用运维：`./scripts/backup.sh` 备份、`docker compose -f docker-compose.prod.yml logs -f api` 看日志。

### 本地开发

```bash
# 1. 启动数据库
docker compose up -d db

# 2. 启动后端
cd apps/api
cp ../../.env.example .env
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 3. 启动前端
cd apps/web
pnpm install
pnpm dev
```

## 项目结构

```text
apps/
├── web/          — Next.js 前端应用
└── api/          — FastAPI 后端应用
docs/             — 项目规格文档
```

## 文档

- [项目需求规格](docs/PROJECT_SPEC.md)
- [UI 规格说明](docs/UI_SPEC.md)
- [RAG 检索规格](docs/RAG_SPEC.md)
- [Agent 工作流规格](docs/AGENT_SPEC.md)
- [开发规则](CLAUDE.md)

## 许可

内部使用
