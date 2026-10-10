# Plimsoll 网站生产运维手册 · 2026-10-04

本文只覆盖**部署文件**（`web/deploy/**`）。计算核心（`tools/plimsoll`）、后端（`web/backend`）、前端（`web/frontend`）源码不在本次改动范围内。

目标主机：Ubuntu 22.04、2 vCPU / 2 GiB、服务器地址 `119.91.211.156`。Docker 29 与 Compose v2.40 已安装，`python:3.12-slim` 与 `postgres:16-alpine` 镜像已拉取。Let's Encrypt IP 证书位于 `/etc/letsencrypt/live/plimsoll-ip/fullchain.pem` 与 `privkey.pem`。

## 当前状态（2026-10-04 公网验收通过）

站点地址 **[https://119.91.211.156](https://119.91.211.156)**，直接用 IP 访问，未绑定域名。

| 项目 | 事实 |
|---|---|
| 发布目录 | `/opt/plimsoll/releases/plimsoll-web-20261004T025804Z-6dea93c` |
| 当前链接 | `/opt/plimsoll/current` 已指向该发布目录 |
| nginx | 已切换到 Plimsoll 站点；旧站点 `dsh.service` 已 `stop`、`disable`，旧单元文件随后在用户授权下删除 |
| 公网 HTTP | 返回 308 跳转到 `https://119.91.211.156` |
| 本机 TLS | 握手通过，证书链可信（有效期 10 月 4 日至 10 月 10 日） |
| 证书续期 | `certbot renew --dry-run` **通过**，全部模拟续期成功 |
| 本机 API | `http://127.0.0.1:18000/api/health` 返回 `status: ok`，匿名认证配置生效 |
| 云安全组 | 腾讯云控制台已放行 TCP 443（来源 `0.0.0.0/0`），规则生效 |
| 公网 HTTPS | **通过**：Windows `curl https://119.91.211.156/api/health` 返回正常，无 `-k`、无证书告警 |
| 公网浏览器 | **通过**：真实浏览器打开 https://119.91.211.156 ，自动获得匿名工作区，建项、改名、保存修订、运行、查看报告、下载 JSON/CSV 全部走通 |
| 备份与恢复 | 每日备份脚本与定时单元已启用并手工触发通过；`pg_restore` 在独立可丢弃数据库中演练通过 |

上线前 443 确实不通（服务器 `tcpdump` 抓到 0 个包）。成因是腾讯云安全组未放行 443 —— 该历史记录属实，控制台放行后即解决。本机 nginx 与 TLS 通过并不能证明链路无中间设备，最终是靠控制台规则与外部复测共同确认的。逐项证据见[生产交接](web-production-handoff-2026-10-04.md)。

## 组件与资源

| 服务 | 镜像 / 命令 | 内存上限 | 端口 |
|---|---|---|---|
| `db` | `postgres:16-alpine`，`max_connections=30`、`shared_buffers=64MB` | 384M | 无（仅 compose 网络） |
| `migrate` | 一次性 `alembic -c web/backend/alembic.ini upgrade head` | 256M | 无 |
| `api` | `uvicorn plimsoll_web.asgi:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*` | 512M | `127.0.0.1:18000` |
| `worker` | `python -m plimsoll_web.worker` | 640M | 无 |

三个 Python 服务共用同一镜像 `plimsoll/runtime:local`，只构建一次。数据库数据在命名卷 `plimsoll_db-data` 中持久化。所有服务日志为 `json-file`，`max-size=10m`、`max-file=3`。

服务器上的实际运行状态：`db` 运行中（384 MiB），`migrate` 已退出 0（256 MiB，一次性），`api` 运行中（512 MiB，仅监听 `127.0.0.1:18000`），`worker` 运行中（640 MiB，单实例）。迁移头为 `6226f03d283f`。数据库不对公网发布端口。

`api` 与 `worker` 依赖 `migrate` 的 `service_completed_successfully`；`migrate` 依赖 `db` 的 `service_healthy`。这一依赖顺序遵循 Compose 的启动顺序机制：<https://docs.docker.com/compose/how-tos/startup-order/>。worker 与 migrate 显式 `healthcheck: disable: true`，因为镜像自带的 `HEALTHCHECK` 探测 `/api/health`，而这两个容器不提供该端点。

常驻容器上限合计 1536 MiB，迁移容器退出后不占常驻预算。Queen Mary 大型 CSV 导出在原 API 256 MiB 上限下触发过容器 OOM，因此 API 上调为 512 MiB、单 worker 为 640 MiB —— 这只是**部署侧资源上限**的修正，没有改动应用代码。在当前 512 MiB 上限下跑完两轮 Queen Mary 大报告导出（正常载荷与满载）后，API 容器重启次数为 0。

## 生产环境变量

秘密只来自 `/etc/plimsoll/production.env`，所有 compose 命令都必须显式带 `--env-file`。文件内不放任何默认口令，缺失变量会让 compose 插值直接失败。秘密只在服务器上生成，本文与交接记录都不写入任何真实口令或密钥。

```bash
sudo install -d -m 750 -o root -g root /etc/plimsoll
sudo cp web/deploy/production.env.example /etc/plimsoll/production.env
sudo chmod 600 /etc/plimsoll/production.env

# 在服务器上生成（URL 安全十六进制，无需转义），输出只留在服务器上
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

**生产发布包必须在干净、已提交的工作区上构建。** 源码在 `6dea93c` 冻结后按下面方式打包：

```powershell
git status --porcelain          # 必须为空
& web/backend/.venv/Scripts/python.exe web/deploy/build_release.py `
  --output .superpowers/releases --confirm-source-frozen
```

`--confirm-source-frozen` 在工作区非干净时直接以退出码 2 拒绝执行；脏工作区构建出的包名带 `-dirty`，manifest 中 `git.dirty` 为 `true`、`source_freeze_confirmed` 为 `false`，工具不会把脏源码标成干净。

产出两个文件：`<时间>-<HEAD7>.tar.gz` 与同名 `.manifest.json`。manifest 记录工具版本、构建时间、git HEAD 与 dirty 标志、归档 SHA-256、文件总数，以及每个文件的路径、字节数和 SHA-256。服务器上可用 `sha256sum` 核对归档。

2026-10-04 实际上线的归档为 `plimsoll-web-20261004T025804Z-6dea93c.tar.gz`：SHA-256 `35bbe801d93227d488b87edeacda2d056f2b282fcddf41d33121974edf341742`；112 个文件，4,661,093 字节是**解包后所有文件的总字节数**，不是压缩包本身的大小。

## 服务器部署

```bash
# 解包到不可变发布目录
RELEASE=plimsoll-web-20261004T025804Z-6dea93c      # 换成实际文件名（去掉 .tar.gz）
sudo install -d -m 755 /opt/plimsoll/releases
sudo tar -xzf /tmp/$RELEASE.tar.gz -C /opt/plimsoll/releases
sudo mv /opt/plimsoll/releases/$RELEASE /opt/plimsoll/releases/$RELEASE.tmp
sudo mv /opt/plimsoll/releases/$RELEASE.tmp /opt/plimsoll/releases/$RELEASE

# 静态站点通过 current 符号链接指向发布目录（nginx root 固定为 current）
sudo ln -sfn /opt/plimsoll/releases/$RELEASE /opt/plimsoll/current

cd /opt/plimsoll/current
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

这些命令已在 2026-10-04 的服务器上执行：`db`、`api`、`worker` 运行中，`migrate` 退出码 0，迁移头 `6226f03d283f`，`/api/health` 返回 `status: ok`。`docker stats` 的实际峰值见交接记录。

## nginx 站点

先做清单，**只替换已命名的那一个旧站点**：

```bash
sudo ls -l /etc/nginx/sites-enabled /etc/nginx/sites-available
sudo grep -rn "server_name" /etc/nginx/sites-enabled /etc/nginx/sites-available
sudo nginx -T | grep -nE "server_name|listen|root "
```

旧站点文件先备份再停用：

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

2026-10-04 已完成切换：`sudo nginx -t` 通过、reload 生效，旧站点服务 `dsh.service` 已 `stop` 并 `disable`（旧单元文件随后在用户授权下删除），外部 HTTP 请求得到 308 跳转到 `https://119.91.211.156`。云安全组放行 443 后，该地址的 HTTPS 与浏览器访问均已通过验收。

### 限流区（已启用）

限流区文件属于 `http` 上下文，而 nginx 默认的 `/etc/nginx/nginx.conf` 已经在 `http` 块里 `include /etc/nginx/conf.d/*.conf;`。因此**只要把文件放进 `conf.d`，`limit_req_zone` 就自动生效**：

```bash
sudo cp web/deploy/nginx/rate-limit-zones.conf /etc/nginx/conf.d/plimsoll-rate-limit-zones.conf
sudo nginx -T | grep -n limit_req_zone      # 确认两个 zone 已在 http 上下文出现
```

**不要再取消 `plimsoll.conf` 里那行 `include /etc/nginx/conf.d/plimsoll-rate-limit-zones.conf;` 的注释。** 它位于 `server` 块内、且 nginx 的 `include` 不会去重，重复引入同一份 `limit_req_zone` 定义会让 `nginx -t` 以 duplicate zone 失败，进而把一次例行限流操作变成停服事故。模板里那行注释只是在强调“先装文件再开限流”的顺序，不是启用开关。

`plimsoll.conf` 中实际生效的只有 API 段那一行 `limit_req zone=plimsoll_general burst=20 nodelay;`（10r/s、burst 20，已启用）。`plimsoll_bootstrap`（1r/s burst 5）只是**定义存在、没有挂到任何 location**，因此当前不生效。真正的匿名建工作区业务限额仍是应用层的 30 次/小时计数器，它是**进程内**的有界节流：API 进程重启即清零，不做持久化登记，所以边缘限流不能被它替代。

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

`pg_dump` 需要在容器内读取 `POSTGRES_USER` / `POSTGRES_DB`，而这两个变量只存在于 `db` 容器的环境里，宿主机 shell 展开不了。必须用 `sh -c` 把展开放到容器内部，并显式关闭标准输入，否则在脚本或自动化里会挂在等待输入上：

```bash
mkdir -p -m 700 /opt/plimsoll/backups
cd /opt/plimsoll/current
umask 077
BACKUP=/opt/plimsoll/backups/plimsoll-db-$(date -u +%Y%m%dT%H%M%SZ).dump
docker compose --env-file /etc/plimsoll/production.env -f web/deploy/compose.yaml \
  exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP" < /dev/null
sha256sum "$BACKUP"
```

恢复演练必须在**独立可丢弃数据库**上进行，绝不覆盖生产库。恢复用 `--no-owner --no-acl`：归档里的属主/ACL 是生产环境的角色名，直接恢复会因为角色不存在而报错：

```bash
# 一次性恢复容器，独立数据卷，不接生产 compose 网络
docker volume create plimsoll_restore_check
docker run -d --name plimsoll-restore -e POSTGRES_PASSWORD=disposable-only \
  -v plimsoll_restore_check:/var/lib/postgresql/data postgres:16-alpine
until docker exec plimsoll-restore pg_isready -U postgres > /dev/null 2>&1; do sleep 1; done
docker cp /opt/plimsoll/backups/<备份>.dump plimsoll-restore:/tmp/restore.dump
docker exec plimsoll-restore pg_restore -U postgres -d postgres --clean --if-exists --no-owner --no-acl /tmp/restore.dump
docker exec plimsoll-restore psql -U postgres -d postgres -c '\dt'
docker rm -f plimsoll-restore && docker volume rm plimsoll_restore_check
```

上面是宿主机上可直接运行的写法。2026-10-04 的实际执行用的是同一个一次性容器加独立数据库 `plimsoll_restore_check`、未挂专用命名卷，结果见下一小节。

### 每日自动备份（已安装）

`/usr/local/sbin/plimsoll-db-backup`（属主 `root:root`，权限 `700`）把上面的备份动作固化成脚本：

- 在 `db` 容器内用 `sh -c` 读取容器环境里的 `POSTGRES_USER` / `POSTGRES_DB`，标准输入以 `</dev/null` 关闭；
- 先写 `.tmp` 临时文件，成功后原子 `rename` 成最终 `.dump`，避免半截文件被当成可用备份；
- 完成后计算并记录 SHA-256；
- 以 `umask 077` 运行，`/opt/plimsoll/backups` 为 `root:root` `700`，普通账号读不到备份。

定时单元已 `enable --now`，并已手工触发验证通过：

```bash
systemctl start plimsoll-db-backup.service      # 手工跑一次
systemctl list-timers plimsoll-db-backup.timer  # 查看下次触发
journalctl -u plimsoll-db-backup.service -n 50  # 查看执行日志
```

```ini
[Timer]
OnCalendar=*-*-* 03:00:00
RandomizedDelaySec=15min
Persistent=true
```

每天 03:00 触发，随机延迟最多 15 分钟；错过的时点在开机后补触发。2026-10-04 核对时 `list-timers` 显示下一次触发为 **2026-10-05 03:10:56 CST**。

**备份保留的诚实边界**：这些备份只存在于这台服务器本地。**没有配置异地/离线副本**，**也没有配置自动清理或保留策略** —— 备份文件会一直累积，需要人工定期删除；不要把它写成“有备份轮转”或“已异地容灾”。

### 2026-10-04 备份与演练结果

备份文件 `/opt/plimsoll/backups/plimsoll-db-20261004T030725Z.dump`，SHA-256 `4a2c89a60bb39ecd7606a58d031ba310d6254af5032fbe449e983820d3426727`。恢复在独立可丢弃数据库 `plimsoll_restore_check` 中进行（与生产完全分离的一次性容器，未挂专用命名卷），`pg_restore` 成功：项目 4、修订 8、运行 5，5 个运行的 `request_fingerprint` 与生产逐条一致，`alembic_version` 与生产一致。演练记录了备份时间、PostgreSQL 版本与迁移版本。

旧站点另存为 `/opt/plimsoll/backups/legacy-dsh-20261004.tar.gz`（约 220 MB）：归档可完整列出，已核对覆盖预期目录（顶层含 `root/the-basement-of-anon` 与 `var/www/dsh`）—— 这是 `tar` 列表层面的核对，不是逐文件内容比对。核对与字面真实路径检查完成后，经用户授权，旧资产**已删除**：旧根仓库 `/root/the-basement-of-anon`、静态站点 `/var/www/dsh`、旧 systemd 单元以及 `sites-available` 中的 `dsh`。归档本身保留，恢复时从该归档进行。

## 可丢弃 PostgreSQL 上的专项测试

PostgreSQL 专项测试读取 `TEST_DATABASE_URL`，必须指向可丢弃实例。生产测试 URL 绝不出现在命令或环境文件里。下面是宿主机上可直接运行的写法：独立容器、独立数据卷，端口映射到回环上的 `55432`，连接串必须用**同一个**映射端口：

```bash
docker run -d --name plimsoll-testdb -p 127.0.0.1:55432:5432 \
  -e POSTGRES_PASSWORD=disposable-only \
  -e POSTGRES_DB=plimsoll_test -e POSTGRES_USER=plimsoll \
  postgres:16-alpine
until docker exec plimsoll-testdb pg_isready -U plimsoll -d plimsoll_test > /dev/null 2>&1; do sleep 1; done
TEST_DATABASE_URL='postgresql+psycopg://plimsoll:disposable-only@127.0.0.1:55432/plimsoll_test' \
  python -m pytest web/backend/tests/test_auth_postgres.py web/backend/tests/test_worker_postgres.py
docker rm -f plimsoll-testdb
```

端口、卷、口令都与生产实例不同。未设置 `TEST_DATABASE_URL` 时这些测试会被跳过，**不得**写成 PostgreSQL 已通过。

2026-10-04 的实际执行方式与上面这个宿主机示例不同：测试库跑在独立 Docker 网络 `plimsoll-acceptance` 里，角色为 `plimsoll_test`，**不映射宿主机端口、不挂宿主机卷**，容器内直连。2 项专项测试**确实执行并通过**，不是跳过。验证完成后可丢弃的 `plimsoll-testdb` 容器与 `plimsoll-acceptance` 网络已删除，生产容器与生产卷未受影响。

恢复演练同样在一次性容器内进行，用独立的 `plimsoll_restore_check` 数据库而不是专用命名卷 —— 见上一节的实际结果说明。

## IP 证书与自动续期

Let's Encrypt 对纯 IP 签发的是**短期证书**，有效期远短于域名证书，续期必须自动化，否则会突然过期。参见 <https://letsencrypt.org/2026/03/11/shorter-certs-certbot/>。

当前签发的证书是真实、可信链的 IP 证书，有效期为 **10 月 4 日至 10 月 10 日**（6 天）。因此续期链路必须先验证通过，不能等到过期才发现。

服务器上实际安装的 timer（每天 00:00 与 12:00 各触发一次，随机延迟最多 30 分钟，错过的时点在开机后补触发，并在开机 15 分钟后先跑一次）：

```bash
sudo tee /etc/systemd/system/plimsoll-certbot-renew.service > /dev/null <<'UNIT'
[Unit]
Description=Renew the Plimsoll Let's Encrypt certificate and reload nginx

[Service]
Type=oneshot
ExecStart=/opt/plimsoll/certbot/bin/certbot renew --quiet
ExecStartPost=/usr/sbin/nginx -t
ExecStartPost=/bin/systemctl reload nginx
UNIT

sudo tee /etc/systemd/system/plimsoll-certbot-renew.timer > /dev/null <<'UNIT'
[Unit]
Description=Try Plimsoll certificate renewal twice a day

[Timer]
OnBootSec=15min
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now plimsoll-certbot-renew.timer
systemctl list-timers plimsoll-certbot-renew.timer
```

**`certbot renew --dry-run` 已执行通过** —— 把 webroot 迁到 `/var/www/acme`（与 nginx 的 ACME `location` 根一致）之后：

```bash
sudo /opt/plimsoll/certbot/bin/certbot renew \
  --dry-run --non-interactive --no-random-sleep-on-renew
```

结果：**通过，全部模拟续期成功。** `--non-interactive` 避免无人值守时卡在提示上，`--no-random-sleep-on-renew` 让演练不睡满随机抖动、尽快出结果。续期链路的验收项已闭环。

续期后证书路径不变，`fullchain.pem` / `privkey.pem` 由 certbot 原地更新。单元先用 `nginx -t` 校验配置再 reload，配置有问题时不会把坏配置推上线；reload 本身不需要额外参数。无需改模板。若将来换域名，需同时更新 `__PLIMSOLL_SERVER_NAME__`、`PLIMSOLL_ALLOWED_ORIGINS` 与证书。

## 匿名模式的用户可见边界

生产以 `PLIMSOLL_AUTH_MODE=anonymous` 运行：首次访问即在浏览器写入匿名会话 Cookie（365 天），无需账号、口令或邮箱，也没有任何邮件（SMTP 未配置）。清除 Cookie、换浏览器或换设备会得到新的工作区，不能自动恢复旧工作区；本地没有跨设备账号找回。请下载项目 JSON 留存输入。在项目库的「从备份恢复」中选择 JSON，先查看只读校验和预览，确认名称后「保存为新项目」。服务端生成新的项目 ID、归属当前工作区并从修订 1 开始，不覆盖备份中的原 ID，不恢复运行记录，也不自动计算。报告 JSON/CSV 是计算输出，不是项目备份，会被拒绝。具体操作见[工作空间流程说明](../formfield/workspace-workflow-2026-10-10.md)。

应用按来源 IP 限制每小时创建 30 个新工作区；已有有效 Cookie 的访问不占用创建额度。每工作区仍只允许一个活动计算，Nginx 限流作为补充。此处没有实现跨设备账号恢复。

本次公网部署发布的是现有计算能力，**不是完整 SPS 复刻**，也不改变计算核心的适用范围边界。

## 验证命令与边界

```powershell
# 本地（PowerShell，仓库根目录）
& web/backend/.venv/Scripts/python.exe -m unittest discover -s web/deploy/tests -v
& web/backend/.venv/Scripts/python.exe web/deploy/build_release.py --output .superpowers/releases
git diff --check
```

已完成的验证：部署文件单元测试在 Windows 上 17 项通过、1 项因无符号链接权限而跳过，在 Linux 上 18 项全部通过。同一防护另有跨平台强制用例覆盖。

**服务器上已验证**：镜像构建、容器启动、数据库迁移（头 `6226f03d283f`，退出码 0）、`/api/health`、匿名工作区的创建与跨 Cookie 隔离（用两个各自独立 Cookie 的 HTTP 客户端交叉验证，不是真实浏览器验收）、`pg_dump`/`pg_restore` 备份与独立数据库恢复演练、每日备份脚本与定时单元（已手工触发通过）、nginx 切换与 308 跳转、本机 TLS 握手、Queen Mary 针对性大报告导出（当前 512 MiB 上限下 API 容器重启 0 次）、`certbot renew --dry-run`（全部模拟续期成功）。

**公网已验证**：外部 HTTPS 访问 `https://119.91.211.156`（`curl` 健康检查通过，无 `-k`、无证书告警）、真实浏览器全流程（自动匿名工作区 → 建项 → 改名并保存修订 → 刷新后仍保留 → 8 个默认阶段全部完成的运行 → 报告 → JSON/CSV 下载）、证书链可信。

**上线过程的历史记录（已解决）**：在腾讯云安全组放行 TCP 443 之前，外部 443 请求在服务器上 `tcpdump` 抓到 0 个包，HTTPS 与浏览器访问均失败；本机 nginx 与 TLS 握手当时已通过。放行后问题消失，说明成因在云侧规则而不是站点配置。

计算核心、后端与前端测试由各自独立验收负责，本手册不重复其结论；核心 746 项是更早一次全量回归的历史数字，本轮部署没有新增核心测试。
