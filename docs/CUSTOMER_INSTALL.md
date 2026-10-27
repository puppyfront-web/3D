# 企业知识助手 — 客户私有化安装指南

> 目标：**30 分钟内** 完成可验收环境（Docker Compose + KB UAT 剧本）。

## 1. 环境要求

| 项 | 要求 |
|----|------|
| 系统 | Linux（推荐 Ubuntu 22.04+）或 macOS |
| Docker | 24+ |
| Docker Compose | v2+ |
| 内存 | 4GB+（推荐 8GB） |
| 磁盘 | 40GB+ |
| 端口 | 3000（前端）、8000（API） |

## 2. 快速安装（POC / UAT）

```bash
git clone <your-repo-url> kb-assistant
cd kb-assistant

cp .env.example .env
# 建议至少设置：
# INITIAL_ADMIN_EMAIL=admin@yourcompany.com
# INITIAL_ADMIN_PASSWORD=<强密码>
# SEED_DEMO_CONTENT=false
# NEXT_PUBLIC_KB_SKU=standard

docker compose up -d --build
docker compose ps
curl -sf http://localhost:8000/health
```

访问：

- 前端：http://localhost:3000  
- API 文档：http://localhost:8000/docs  

管理员账号来自 `.env` 的 `INITIAL_ADMIN_*`（首次启动写入，幂等）。

若需本地快速体验演示案例，可临时 `SEED_DEMO_CONTENT=true` 后重启 API（**生产禁止**）。

## 3. 生产安装

```bash
cp .env.example .env
# POSTGRES_PASSWORD、SECRET_KEY、INITIAL_ADMIN_*、LLM/EMBEDDING 密钥

./deploy.sh
# 或：docker compose -f docker-compose.prod.yml up -d --build
```

详见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

## 4. 知识库相关配置

| 变量 | 说明 | 建议 |
|------|------|------|
| `KB_SKU` / `NEXT_PUBLIC_KB_SKU` | `standard` 收束 Admin 菜单 | 交付默认 standard |
| `SEED_DEMO_CONTENT` | 演示案例/SOP 种子 | 生产 `false` |
| `WEB_SEARCH_ENABLED` | 联网补充 | 内网可 `false` |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | 模型 | 生产用真实 API |

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-your-key
EMBEDDING_MODEL=text-embedding-3-small
```

修改后：`docker compose restart api`

## 5. 验收检查清单（KB 交付）

- [ ] `curl http://localhost:8000/health` 正常  
- [ ] 管理员可登录 `/login`  
- [ ] `/admin/assets` 上传并成功入库（或导入 Knowledge Pack ZIP）
- [ ] `/admin/rag-test` 能命中资料  
- [ ] `/admin/eval` 可 Run 评测集（可先「导入交付冒烟模板」）  
- [ ] 创建项目后在 `/workspace/chat/{id}` 问答，答案带引用  
- [ ] `/admin/retrieval-logs` 有记录  
- [ ] 按 [DEMO.md](./DEMO.md) 走完 UAT 表  

## 6. 自动化冒烟（可选）

在 API 容器或本地 venv：

```bash
cd apps/api
pytest app/tests/test_knowledge_qa_flow.py app/tests/test_kb_m1.py app/tests/test_eval_run.py app/tests/test_knowledge_pack.py -q
```

## 7. 本期交付范围（KB-Case v1）

| 里程碑 | 包含 |
|--------|------|
| M1 | 私有化安装、Admin 写鉴权、KB SKU、问答↔检索日志、E2E |
| M2 | 检索实验室（含 Context Pack 预览）、评测中心、Lab→用例、冒烟模板 |
| M3 | Knowledge Pack 导入、分块预览、Admin 首次引导 |
| M5 | 脱敏参考包（见下） |

**不含（后续迭代）**：M4 Review 队列、Analytics 看板、query_synonyms、多租户。

### 参考 Knowledge Pack（UAT 可选）

```bash
./scripts/build_reference_pack.sh
# 生成 delivery/reference-b2b-demo.zip
# 在 /admin/assets →「导入 Knowledge Pack」上传
```

## 8. 备份（生产）

```bash
./scripts/backup.sh
```

## 9. 故障排查

| 问题 | 排查 |
|------|------|
| API 启动失败 | `docker compose logs api`，检查 Alembic 是否到 head |
| 前端无法调 API | `NEXT_PUBLIC_API_URL`、CORS、浏览器 Network |
| 检索始终为空 | 资料是否 indexed；Embedding 是否配置 |
| Eval 全失败 | 用例关键词与资料不一致，在 Lab 保存用例 |

技术支持请附带 `docker compose logs api` 末 50 行。
