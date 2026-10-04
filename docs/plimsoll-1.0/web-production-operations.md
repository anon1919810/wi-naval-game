# Plimsoll 网站生产运维手册 · 2026-10-04

本文只覆盖**部署文件**（`web/deploy/**`）。计算核心（`tools/plimsoll`）、后端（`web/backend`）、前端（`web/frontend`）源码不在本次改动范围内。

目标主机：Ubuntu 22.04、2 vCPU / 2 GiB、服务器地址 `119.91.211.156`。Docker 29 与 Compose v2.40 已安装，`python:3.12-slim` 与 `postgres:16-alpine` 镜像已拉取，nginx 已在 80 端口运行旧站点（旧站点已备份），证书位于 `/etc/letsencrypt/live/plimsoll-ip/fullchain.pem` 与 `privkey.pem`。

**当前状态：文件已产出，尚未在服务器上真实部署。** 镜像构建、容器启动、迁移、nginx 切换与证书续期都属于 Codex 在服务器上的远端验收，本手册中的命令尚未实际执行过，不能当作已验证结论。旧站点备份已完成，但新站点尚未接管流量。

## 组件与资源

| 服务 | 镜像 / 命令 | 内存上限 | 端口 |
|---|---|---|---|
| `db` | `postgres:16-alpine`，`max_connections=30`、`shared_buffers=64MB` | 384M | 无（仅 compose 网络） |
| `migrate` | 一次性 `alembic -c web/backend/alembic.ini upgrade head` | 256M | 无 |
| `api` | `uvicorn plimsoll_web.asgi:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*` | 512M | `127.0.0.1:18000` |
| `worker` | `python -m plimsoll_web.worker` | 640M | 无 |

三个 Python 服务共用同一镜像 `plimsoll/runtime:local`，只构建一次。数据库数据在命名卷 `plimsoll_db-data` 中持久化。所有服务日志为 `json-file`，`max-size=10m`、`max-file=3`。

`api` 与 `worker` 依赖 `migrate` 的 `service_completed_successfully`；`migrate` 依赖 `db` 的 `service_healthy`。这一依赖顺序遵循 Compose 的启动顺序机制：<https://docs.docker.com/compose/how-tos/startup-order/>。worker 与 migrate 显式 `healthcheck: disable: true`，因为镜像自带的 `HEALTHCHECK` 探测 `/api/health`，而这两个容器不提供该端点。

常驻容器上限合计 1536 MiB，迁移容器退出后不占常驻预算。Queen Mary 大型 CSV 导出在原 API 256 MiB 上限下触发了容器 OOM，因此 API 调整为 512 MiB，单 worker 为 640 MiB。实际运行峰值仍需测量，并保留每次发布的验收记录。

## 生产环境变量

秘密只来自 `/etc/plimsoll/production.env`，所有 compose 命令都必须显式带 `--env-file`。文件内不放任何默认口令，缺失变量会让 compose 插值直接失败。

```bash
sudo install -d -m 750 -o root -g root /etc/plimsoll
sudo cp web/deploy/production.env.example /etc/plimsoll/production.env
sudo chmod 600 /etc/plimsoll/production.env

# 在服务器上生成（URL 安全十六进制，无需转义）
openssl rand -hex 24   # -> POSTGRES_PASSWORD
openssl rand -hex 32   # -> PLIMSOLL_SECRET_KEY

sudoedit /etc/plimsoll/production.env
```

必需项：

| 变量 | 说明 |
|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` | 数据库名与角色名 |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` 输出，只用十六进制，避免 URL 转义问题 |
| `PLIMSOLL_ALLOWED_ORIGINS` | 浏览器实际 Origin，无结尾斜杠：`https://119.91.211.156` 或 `https://域名` |
| `PLIMSOLL_SECRET_KEY` | `openssl rand -hex 32` 输出 |

生产**不设置** `PLIMSOLL_SMTP_*`、`PLIMSOLL_LOCAL_HTTP`、`PLIMSOLL_LOCAL_MAIL_TEST`。匿名工作区不发邮件，这两个本地开关也绝不能带到公网。compose 内固定 `PLIMSOLL_AUTH_MODE=anonymous`，这是明确的生产认证模式。

数据库 URL 由 compose 组装为 `postgresql+psycopg://<user>:<hex>@db:5432/<db>`，只在内网容器网络内使用。

## 发布包构建（本地）

前端不在此步骤构建，`web/frontend/dist/` 必须已存在且含 `index.html`。归档只取白名单输入：`tools/plimsoll` 与 `web/backend` 的 git 已跟踪文件（自动排除 `tests/`、`.venv/`、`__pycache__/`、`.pytest_cache/`、`*.egg-info`、`.env`、`production.env`、密钥与数据库文件）、显式列出的 `web/deploy` 文件、以及编译产物 `web/frontend/dist`。不会打包整个 checkout，因此游戏资产、研究笔记、`.superpowers/`、本地数据库和用户数据都不会进入归档。

```powershell
# 1) 前端产物（若尚未构建）
npm.cmd --prefix web/frontend run build

# 2) 部署文件单元测试
& web/backend/.venv/Scripts/python.exe -m unittest discover -s web/deploy/tests -v

# 3) 打包（输出到 .superpowers/releases，已被 git 忽略）
& web/backend/.venv/Scripts/python.exe web/deploy/build_release.py --output .superpowers/releases
```

**源码冻结必须由运维确认。** 匿名认证相关源码当前仍在改动，最终发布前必须先提交，然后确认冻结：

```powershell
git status --porcelain          # 必须为空
& web/backend/.venv/Scripts/python.exe web/deploy/build_release.py `
  --output .superpowers/releases --confirm-source-frozen
```

`--confirm-source-frozen` 在工作区非干净时直接以退出码 2 拒绝执行；脏工作区构建出的包名带 `-dirty`，manifest 中 `git.dirty` 为 `true`、`source_freeze_confirmed` 为 `false`，工具不会把脏源码标成干净。

产出两个文件：`<时间>-<HEAD7>.tar.gz` 与同名 `.manifest.json`。manifest 记录工具版本、构建时间、git HEAD 与 dirty 标志、归档 SHA-256、文件总数，以及每个文件的路径、字节数和 SHA-256。服务器上可用 `sha256sum` 核对归档。

## 服务器部署

```bash
# 解包到不可变发布目录
RELEASE=plimsoll-web-20261004T024335Z-8da4f20      # 换成实际文件名（去掉 .tar.gz）
sudo install -d -m 755 /opt/plimsoll/releases
sudo tar -xzf /tmp/$RELEASE.tar.gz -C /opt/plimsoll/releases
sudo mv /opt/plimsoll/releases/$RELEASE /opt/plimsoll/releases/$RELEASE.tmp
sudo mv /opt/plimsoll/releases/$RELEASE.tmp /opt/plimsoll/releases/$RELEASE

# 静态站点通过 current 符号链接指向发布目录（nginx root 固定为 current）
sudo ln -sfn /opt/plimsoll/releases/$RELEASE /opt/plimsoll/current

cd /opt/plimsoll/releases/$RELEASE
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml config --quiet
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml build api
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml up -d
```

`compose.yaml` 位于 `web/deploy`，因此构建上下文是 `../..`（发布根目录），Dockerfile 路径仍为 `web/deploy/Dockerfile`。这保证上下文里只有白名单文件，没有 `node_modules/` 与 `.venv/`。

`up -d` 会自动先跑 `migrate`：数据库健康后执行 `alembic upgrade head`，退出码 0 之后才启动 `api` 与 `worker`。迁移失败则两者都不启动。手动重跑迁移（幂等）：

```bash
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml run --rm migrate
```

查看状态与日志：

```bash
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml ps -a
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml logs --tail=100 api worker
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml logs migrate
curl -fsS http://127.0.0.1:18000/api/health      # 期望 {"status":"ok",...}
```

镜像与容器层面尚未在真实服务器验证；上面的健康检查与 `docker stats` 观察都属于远端验收步骤。

## nginx 站点

先做清单，**只替换已命名的那一个旧站点**：

```bash
sudo ls -l /etc/nginx/sites-enabled /etc/nginx/sites-available
sudo grep -rn "server_name" /etc/nginx/sites-enabled /etc/nginx/sites-available
sudo nginx -T | grep -nE "server_name|listen|root "
```

旧站点文件先备份再停用（备份已在此前完成，仍保留一份带时间戳的副本）：

```bash
sudo cp -a /etc/nginx/sites-available/<旧站点名> /root/nginx-backup-<旧站点名>-$(date +%Y%m%d%H%M%S)
```

渲染模板并安装。四个占位符必须全部替换，`__PLIMSOLL_SERVER_NAME__` 填 IP 或域名，与证书和 `PLIMSOLL_ALLOWED_ORIGINS` 保持一致：

```bash
sudo install -d -m 755 /var/www/acme/.well-known/acme-challenge
sudo sed -e "s|__PLIMSOLL_SERVER_NAME__|119.91.211.156|g" \
         -e "s|__PLIMSOLL_TLS_CERT__|/etc/letsencrypt/live/plimsoll-ip/fullchain.pem|g" \
         -e "s|__PLIMSOLL_TLS_KEY__|/etc/letsencrypt/live/plimsoll-ip/privkey.pem|g" \
         -e "s|__PLIMSOLL_ACME_ROOT__|/var/www/acme|g" \
         web/deploy/nginx/plimsoll.conf.template \
  | sudo tee /etc/nginx/sites-available/plimsoll.conf > /dev/null

sudo ln -sfn /etc/nginx/sites-available/plimsoll.conf /etc/nginx/sites-enabled/plimsoll.conf
sudo nginx -t && sudo systemctl reload nginx
```

**证书文件存在之前不要安装 HTTPS 段。** `nginx -t` 会因找不到证书而失败，`systemctl reload` 被拒绝，旧站点继续服务。顺序应为：先确认 `fullchain.pem` 与 `privkey.pem` 存在 → `nginx -t` 通过 → 再 reload。

模板行为：

- `/api/` 反代到 `http://127.0.0.1:18000`，`proxy_pass` 不带尾部 URI，前缀原样保留；`X-Forwarded-For` 用 `$remote_addr` **覆盖**，不接受客户端传入的伪造链。
- `/api` 精确匹配 308 到 `/api/`；未知 `/api` 路径由 FastAPI 返回 404，不会落到 SPA。
- SPA 回退只作用于非 `/api` 路径；`/assets/` 为带哈希产物，`max-age=31536000, immutable`；`/index.html` 为 `no-cache`，保证发布后立即生效。
- `client_max_body_size 8m`，与应用 8 MiB 请求体上限一致。
- 80 端口只放行 ACME 挑战，其余 308 到**规范主机名**（渲染后的 `__PLIMSOLL_SERVER_NAME__`）。刻意不使用 `$host`：那会让未知 Host 头把访问者重定向到攻击者域名。

可选限流（应用层匿名计数器 30 次/小时才是真正的业务限额）：

```bash
sudo cp web/deploy/nginx/rate-limit-zones.conf /etc/nginx/conf.d/plimsoll-rate-limit-zones.conf
# 然后取消 plimsoll.conf 中 include 与 limit_req 行的注释，重新 nginx -t && reload
```

`plimsoll_general` 为 10r/s burst 20，`plimsoll_bootstrap` 为 1r/s burst 5。

## 回滚

发布目录不可变，回滚只切 `current` 符号链接并重启应用容器，**不回滚数据库**：

```bash
cd /opt/plimsoll/releases/<旧发布名>
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml up -d
sudo ln -sfn /opt/plimsoll/releases/<旧发布名> /opt/plimsoll/current
sudo nginx -t && sudo systemctl reload nginx
```

禁止事项：`docker compose down -v` 会删除 `plimsoll_db-data` 卷，生产环境一律不用；`down` 也只在需要重建容器时使用。数据库迁移**不做降级**：Alembic 只向前。若新版本迁移后必须回退应用，先恢复到备份（见下节）再启动旧版本，或保持新版本并修复问题。

## 备份与恢复

```bash
# 备份（Fc 自定义格式）
mkdir -p /var/backups/plimsoll
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml \
  exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > /var/backups/plimsoll/plimsoll-$(date +%Y%m%d%H%M%S).dump
```

恢复演练必须在**独立可丢弃数据库**上进行，绝不覆盖生产库：

```bash
# 一次性恢复容器，独立数据卷，不接生产 compose 网络
docker volume create plimsoll_restore_check
docker run -d --name plimsoll-restore -e POSTGRES_PASSWORD=disposable-only \
  -v plimsoll_restore_check:/var/lib/postgresql/data postgres:16-alpine
until docker exec plimsoll-restore pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
docker cp /var/backups/plimsoll/<备份>.dump plimsoll-restore:/tmp/restore.dump
docker exec plimsoll-restore pg_restore -U postgres -d postgres --clean --if-exists /tmp/restore.dump
docker exec plimsoll-restore psql -U postgres -d postgres -c '\dt'
docker rm -f plimsoll-restore && docker volume rm plimsoll_restore_check
```

备份需与数据库分开存放，并记录备份时间、PostgreSQL 版本、`alembic_version` 内容与演练结果。

## 可丢弃 PostgreSQL 上的专项测试

PostgreSQL 专项测试读取 `TEST_DATABASE_URL`，必须指向可丢弃实例。生产测试 URL 绝不出现在命令或环境文件里。用独立 compose 项目名与独立卷：

```bash
docker run -d --name plimsoll-testdb -e POSTGRES_PASSWORD=disposable-only \
  -e POSTGRES_DB=plimsoll_test -e POSTGRES_USER=plimsoll \
  postgres:16-alpine
until docker exec plimsoll-testdb pg_isready -U plimsoll -d plimsoll_test > /dev/null 2>&1; do sleep 1; done
TEST_DATABASE_URL='postgresql+psycopg://plimsoll:disposable-only@127.0.0.1:5432/plimsoll_test' \
  python -m pytest web/backend/tests/test_auth_postgres.py web/backend/tests/test_worker_postgres.py
docker rm -f plimsoll-testdb
```

（需自行加 `-p 127.0.0.1:55432:5432` 之类的端口映射；测试实例与生产实例端口、数据卷、密码均不相同。未设置 `TEST_DATABASE_URL` 时这些测试会被跳过，**不得**写成 PostgreSQL 已通过。）

## IP 证书与自动续期

Let's Encrypt 对纯 IP 签发的是**短期证书**，有效期远短于域名证书，续期必须自动化，否则会突然过期。参见 <https://letsencrypt.org/2026/03/11/shorter-certs-certbot/>。

用 systemd timer 每 12 小时尝试续期，成功后重载 nginx：

```bash
sudo tee /etc/systemd/system/plimsoll-certbot-renew.service > /dev/null <<'UNIT'
[Unit]
Description=Renew the Plimsoll Let's Encrypt certificate and reload nginx

[Service]
Type=oneshot
ExecStart=/opt/plimsoll/certbot/bin/certbot renew --quiet
ExecStartPost=/usr/bin/systemctl reload nginx
UNIT

sudo tee /etc/systemd/system/plimsoll-certbot-renew.timer > /dev/null <<'UNIT'
[Unit]
Description=Try Plimsoll certificate renewal every 12 hours

[Timer]
OnBootSec=15min
OnUnitActiveSec=12h
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now plimsoll-certbot-renew.timer
systemctl list-timers plimsoll-certbot-renew.timer
sudo /opt/plimsoll/certbot/bin/certbot renew --dry-run
```

续期后证书路径不变，`fullchain.pem` / `privkey.pem` 由 certbot 原地更新，nginx reload 即可生效，无需改模板。若将来换域名，需同时更新 `__PLIMSOLL_SERVER_NAME__`、`PLIMSOLL_ALLOWED_ORIGINS` 与证书。

## 匿名模式的用户可见边界

生产以 `PLIMSOLL_AUTH_MODE=anonymous` 运行：首次访问即在浏览器写入匿名会话 Cookie（365 天），无需账号、口令或邮箱。清除 Cookie、换浏览器或换设备会得到新的工作区，不能自动恢复旧工作区。请下载项目 JSON 留存输入；手工恢复时先创建新项目，将备份顶层 `id` 改为新项目的 `id`，然后在「完整项目数据」中应用并保存。报告 JSON/CSV 不是项目备份。应用按来源 IP 限制每小时创建 30 个新工作区；已有有效 Cookie 的访问不占用创建额度。每工作区仍只允许一个活动计算，Nginx 限流作为补充。此处没有实现跨设备账号恢复。

## 验证命令与边界

```powershell
# 本地（PowerShell，仓库根目录）
& web/backend/.venv/Scripts/python.exe -m unittest discover -s web/deploy/tests -v
& web/backend/.venv/Scripts/python.exe web/deploy/build_release.py --output .superpowers/releases
git diff --check
```

已完成的本地验证：部署文件单元测试 17 项通过、1 项因 Windows 无符号链接权限而跳过；同一防护另有跨平台强制用例覆盖。发布包构建成功，开发归档与 manifest 明确保留 `dirty` 标志，正式上线必须另建冻结归档。

**未验证**：Docker 镜像构建、容器启动、数据库迁移、nginx 切换、证书续期与真实流量，全部需要 Codex 在服务器上执行。计算核心、后端与前端测试由各自会话负责，本手册不重复其结论，也不代表核心仍通过全部历史回归。
