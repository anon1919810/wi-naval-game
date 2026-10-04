# Plimsoll 网站本地运行与交接 · 2026-09-23

这份文档对应 `feature/plimsoll-1.0` 的本地网站首版。它提供邮箱验证码入口、逐用户私有舰船项目、不可变修订、后台计算、JSON/CSV 导出及站内报告。计算核心仍是类 SPS 阶段成果；“完成”表示已请求阶段完成，不代表史实验证或适航认证。Queen Mary 是标明估算和缺项的工程代理。

（历史记录）网站当时未在公网部署，Unity 游戏、桌面资产仓库和服务器均未修改。上线前列出的前置条件里，**有效邮件发送服务已不再是必需项** —— 生产改用匿名模式，不发邮件、不做邮箱登录；HTTPS、PostgreSQL 集成验收、备份与运维监控仍然需要。不要把 `PLIMSOLL_LOCAL_HTTP` 或 `PLIMSOLL_LOCAL_MAIL_TEST` 用于公网。

> **2026-10-04 更新**：本文描述的是本地首版运行方式，保留为开发入口，其中的上线前置条件按上面的历史记录理解。生产部署已完成并通过公网验收，站点地址 **[https://119.91.211.156](https://119.91.211.156)**（IP 直连，未绑定域名）。生产以匿名模式运行，与本文的邮箱验证码流程不同：没有邮箱、没有登录、没有邮件。见[生产部署交接](web-production-handoff-2026-10-04.md)与[生产运维手册](web-production-operations.md)。

## 目录与要求

- `tools/plimsoll/`：计算与项目契约；网站调用同一计算核心。
- `web/backend/`：FastAPI、SQLAlchemy、Alembic、一个独立工作进程。
- `web/frontend/`：React/Vite，浅色默认、账户级深色偏好。
- Python 3.12、Node.js 22 或兼容版本、npm。使用一个本地 PostgreSQL 实例作为正式集成目标；SQLite 只供个人本地演示和部分测试，不能代替并发验收。

以下 PowerShell 命令均从仓库根目录执行。先建立 Python 环境：

```powershell
python -m venv web/backend/.venv
& 'web/backend/.venv/Scripts/python.exe' -m pip install -e './web/backend[dev]'
npm.cmd --prefix web/frontend ci
```

本地演示可暂用 SQLite。每个运行 API 或工作进程的 PowerShell 窗口都设置相同数据库地址、密钥和 `PYTHONPATH`；密钥仅在当前终端会话中使用，不写入仓库：

```powershell
$env:PYTHONPATH = 'tools'
$env:PLIMSOLL_DATABASE_URL = 'sqlite+pysqlite:///./plimsoll-local.db'
$env:PLIMSOLL_SECRET_KEY = (& 'web/backend/.venv/Scripts/python.exe' -c 'import secrets; print(secrets.token_urlsafe(48))')
$env:PLIMSOLL_ALLOWED_ORIGINS = 'http://127.0.0.1:5173'
$env:PLIMSOLL_LOCAL_HTTP = '1'
$env:PLIMSOLL_LOCAL_MAIL_TEST = '1'
```

本地测试邮件模式**只接受回环地址和 HTTP**。验证码只写在 API 终端标准输出，绝不通过网页返回。`PLIMSOLL_LOCAL_MAIL_TEST=1` 是显式测试开关；不设置它且未配置 SMTP 时，邮件请求会失败而不会假装发送成功。若从另一个终端启动 worker，复制相同的数据库地址即可；worker 不发送邮件。生产应使用 SMTP，并保持安全 Cookie：

| 变量 | 用途 |
|---|---|
| `PLIMSOLL_DATABASE_URL` | SQLAlchemy 数据库 URL；公开部署用 PostgreSQL |
| `PLIMSOLL_SECRET_KEY` | 会话相关密钥；仅通过环境变量注入 |
| `PLIMSOLL_ALLOWED_ORIGINS` | 允许写请求的准确 Origin，逗号分隔 |
| `PLIMSOLL_SMTP_HOST` / `PLIMSOLL_SMTP_PORT` | 邮件服务器；默认端口 465 |
| `PLIMSOLL_SMTP_SENDER` / `PLIMSOLL_SMTP_USERNAME` / `PLIMSOLL_SMTP_PASSWORD` | 发件身份与认证 |
| `PLIMSOLL_LOCAL_HTTP` | 仅回环开发时允许非 Secure Cookie |
| `PLIMSOLL_LOCAL_MAIL_TEST` | 仅回环开发时把验证码打印到 API 终端 |

先执行版本化迁移，再分别启动 API、一个 worker 和前端开发服务器：

```powershell
& 'web/backend/.venv/Scripts/python.exe' -m alembic -c web/backend/alembic.ini upgrade head
& 'web/backend/.venv/Scripts/python.exe' -m uvicorn plimsoll_web.asgi:app --host 127.0.0.1 --port 8000
```

第二个终端运行 `& 'web/backend/.venv/Scripts/python.exe' -m plimsoll_web.worker`；第三个终端运行 `npm.cmd --prefix web/frontend run dev`。浏览器打开 `http://127.0.0.1:5173`。邮箱验证后从 API 终端读取六位码。一次只启动一个 worker；先量测并发和内存再增加。

生产构建用 `npm.cmd --prefix web/frontend run build`，生成 `web/frontend/dist/`。服务端只接收 `/api`，静态站点与 API 应由同一 HTTPS Origin 反向代理，写请求 Origin 与 `PLIMSOLL_ALLOWED_ORIGINS` 一致。

## 检查与故障定位

1. `GET http://127.0.0.1:8000/api/health` 应返回 `status: ok`。
2. 邮箱登录后在项目库建立解析方箱、通用船或 Queen Mary。Queen Mary 的“史实未认证代理”是数据适用性提示，不是项目读取失败。
3. 修改主尺度后先“保存修订”；草稿未保存时不允许运行。修订冲突可复制当前草稿并重新载入。
4. 选择工况、运行；排队/计算中由页面轮询。刷新页面后从项目的“最近运行”重新进入。完成后打开报告并下载 JSON/CSV，两者的 `request_fingerprint` 与运行页一致。
5. 运行失败或 worker 丢失时，查看运行页的 `error.code`、`error.message`，并查看 API/worker 的标准输出。`partial`、`model_limit`、`unavailable`、`not_requested` 均保留原义，不自动变成零或通过。

当前请求体上限为 8 MiB，单账号同时只允许一个排队或执行中的运行；工作进程的子进程有时限及结果体积限制。反向代理上线时还应设置请求体和超时上限。项目和计算结果在数据库中；服务日志在运行它们的终端标准输出，开发模式验证码也在那里。

请求体按流累计，到达上限即停止读取并返回 413。单次计算的子进程时限为 120 秒，运行租约另留 30 秒收尾余量；若 worker 异常退出，在租约到期后，下一次运行查询或新运行请求会将旧运行记为 `failed`、`run.worker_lost`，解除该账号的运行占用。SMTP 隐式 TLS 与 STARTTLS 均校验证书和主机名。

## 备份与恢复

在 PostgreSQL 上，使用常规 `pg_dump -Fc` 备份指定数据库，并用 `pg_restore` 在**独立测试库**恢复；记录备份时间、数据库版本、迁移版本及恢复演练结果。备份必须包含用户、验证码/会话状态、项目、修订和运行结果，且存储位置与数据库分开。恢复后先运行迁移，再用测试账号核对一个旧项目的修订和运行指纹，不在生产库上做恢复演练。SQLite 演示时停止 API/worker 后再复制数据库文件；复制运行中的单文件并非可靠备份。

## 验证命令与边界

```powershell
$env:PYTHONPATH = 'tools'
& 'web/backend/.venv/Scripts/python.exe' -m pytest web/backend/tests -q
& 'web/backend/.venv/Scripts/python.exe' -B tools/plimsoll/run_all_tests.py
npm.cmd --prefix web/frontend test -- --reporter=dot
npm.cmd --prefix web/frontend run build
```

PostgreSQL 专用测试读取 `TEST_DATABASE_URL`，应指向可丢弃的测试数据库，再运行 `web/backend/tests/test_auth_postgres.py` 与 `web/backend/tests/test_worker_postgres.py`。未设置它时，测试被跳过，**不能**写成 PostgreSQL 已通过。此首版不包括公网部署、QQ 登录、公开项目、多人编辑和 PDF 服务端生成；浏览器的“打印报告”提供打印/PDF 输出。

## 2026-09-23 本地验收记录

| 检查 | 结果 |
|---|---|
| 后端全套（含 PostgreSQL 专项） | 独立审查修复后 35/35 通过；第三方 TestClient 发出 1 条弃用警告 |
| PostgreSQL 17.11 临时实例 | Alembic `6226f03d283f` 迁移成功；验证码并发一次性消费与队列独占领取 2/2 通过 |
| 计算核心全量回归 | 700/700 通过，`PLIMSOLL_REGRESSION run=700 fail=0`；约 322 秒 |
| 前端 | 独立审查修复后 13/13 通过；TypeScript 与 Vite 生产构建成功 |
| 浏览器实际流程 | 回环测试邮箱注册登录 → Queen Mary 建项 → 型宽修改与修订 2 → 正常载荷后台计算 → 报告 → JSON 导出 HTTP 200 → 刷新并重开项目和运行，均通过 |
| 备份恢复演练 | PostgreSQL `pg_dump -Fc` → 独立 `plimsoll_restore` 数据库 `pg_restore`，原库与恢复库的同一运行指纹一致 |

验收账号、数据库和验证码仅用于本机临时实例。验收展示的 Queen Mary 输入仍是工程代理，报告明确标为史实未认证。当前还没有公网 HTTPS、真实邮件服务、跨机器负载与持久运维监控证据。

独立代码审查指出的六处问题已用先失败后通过的针对性测试处理：隐式 TLS 校验、保存中的草稿保护、不完整 JSON 的渲染前校验、无 worker 时的过期运行恢复、无 `Content-Length` 请求体的流式上限，以及阻力/轴功率报告行。计算核心未修改，因此 700 项核心回归不重复运行；最终后端与前端套件的数字以上表为准。
