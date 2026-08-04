# 企业知识库与方案问答助手

面向企业私有化部署的**知识库运营 + 可追溯问答**平台：资料上传入库、混合检索、项目级问答，输出带引用的结论与方案建议。

## 产品形态

- **知识库运营后台** — 资料上传、入库、案例/话术、检索测试
- **项目工作台** — 按项目隔离资料与对话
- **知识问答** — KB-first 检索，返回答案与参考来源
- **混合 RAG** — 向量 + 关键词 + 结构化案例检索

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

## 演示与客户交付

| 文档 | 说明 |
|------|------|
| [客户私有化安装指南](docs/CUSTOMER_INSTALL.md) | Docker 30 分钟 POC 部署 |
| [演示脚本（§14.1）](docs/DEMO.md) | 华为裸眼 3D 标准演示剧本 |
| [售前交付验收规格](docs/PRESALE_DELIVERY_SPEC.md) | 端到端验收清单 |

默认演示账号：`admin@3dwall.com` / `admin123`（首次登录后请改密）。  
API 启动后会自动写入 3 条演示案例（标签 `presale_demo_seed`）及 `default_presale_sop`。

## 文档

- [项目需求规格](docs/PROJECT_SPEC.md)
- [UI 规格说明](docs/UI_SPEC.md)
- [RAG 检索规格](docs/RAG_SPEC.md)
- [Agent 工作流规格](docs/AGENT_SPEC.md)
- [开发规则](CLAUDE.md)

## 许可

内部使用
