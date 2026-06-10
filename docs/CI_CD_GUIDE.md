# GitHub Actions 自动部署到阿里云 — 配置指南

## 概述

代码推送到 `main` 分支时，GitHub Actions 自动通过 SSH 连接阿里云服务器，拉取最新代码并重新部署。

```
开发者 git push → GitHub Actions 触发 → SSH 连接阿里云 → git pull → docker build → docker up → 健康检查
```

## 前置条件

1. **阿里云 ECS 服务器**已初始化（Docker + Docker Compose 已安装）
2. 服务器上已手动完成首次部署（`.env` 已配置，代码已 clone）
3. GitHub 仓库已有 `main` 分支

## 配置步骤

### Step 1: 服务器准备 SSH 密钥

在阿里云服务器上：

```bash
# 生成专用部署密钥（如果还没有）
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deploy_key

# 将公钥加入 authorized_keys
cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys

# 查看私钥内容（下一步要用）
cat ~/.ssh/deploy_key
```

### Step 2: 配置 GitHub Secrets

进入 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

添加以下 4 个 Secret：

| Secret 名称 | 值 | 说明 |
|-------------|-----|------|
| `ALIYUN_HOST` | `47.xxx.xxx.xxx` | 阿里云服务器公网 IP |
| `ALIYUN_USER` | `root` | SSH 登录用户名 |
| `ALIYUN_SSH_KEY` | `-----BEGIN OPENSSH PRIVATE KEY-----...` | Step 1 生成的私钥完整内容 |
| `ALIYUN_DEPLOY_PATH` | `/opt/3d-wall` | 服务器上项目部署路径 |

### Step 3: 首次手动部署

在阿里云服务器上执行首次部署（Actions 只负责后续更新）：

```bash
# 安装 Docker（如果未安装）
curl -fsSL https://get.docker.com | sh

# 克隆代码
cd /opt
git clone https://github.com/puppyfront-web/3D.git 3d-wall
cd 3d-wall

# 配置环境
cp .env.example .env
nano .env  # 编辑配置（参考 DEPLOYMENT.md）

# 首次部署
chmod +x deploy.sh
./deploy.sh
```

### Step 4: 验证自动部署

```bash
# 在本地修改代码并推送
git push origin main

# 进入 GitHub → Actions 标签页查看运行状态
# 或在服务器上查看日志
tail -f /var/log/syslog | grep docker
```

## 工作流文件说明

文件位置：`.github/workflows/deploy.yml`

```yaml
触发条件:
  - push 到 main 分支
  - 手动触发（workflow_dispatch）

执行流程:
  1. SSH 连接阿里云服务器
  2. git fetch + reset 到最新 main
  3. docker compose build（并行构建）
  4. docker compose up -d（滚动更新）
  5. 等待 15 秒后健康检查
```

## 安全建议

1. **SSH 密钥**：使用专用部署密钥，不要用个人密钥
2. **防火墙**：阿里云安全组只开放 22（SSH）、80、443 端口
3. **.env 保护**：`.env` 文件只在服务器上存在，不进入 Git
4. **最小权限**：可创建专用部署用户替代 root

```bash
# 创建专用部署用户（可选）
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/3d-wall
sudo chown deploy:deploy /opt/3d-wall
```

## 常见问题

### Q: Actions 报 "Permission denied"

检查 SSH 密钥配置：
```bash
# 在服务器上测试
ssh -i ~/.ssh/deploy_key root@localhost "echo ok"
```

### Q: docker compose 命令失败

确认服务器 Docker Compose 版本：
```bash
docker compose version  # 需要 v2+
```

### Q: 构建超时

阿里云服务器网络可能较慢，考虑：
1. 配置 Docker Hub 镜像加速
2. 在服务器上预拉取基础镜像：`docker pull python:3.12-slim && docker pull node:20-alpine`

### Q: 如何回滚

```bash
# SSH 到服务器
cd /opt/3d-wall
git log --oneline -5  # 找到上一个正常版本
git reset --hard <commit-hash>
docker compose -f docker-compose.prod.yml up -d --build
```
