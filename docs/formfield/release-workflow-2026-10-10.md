# 工作空间流程与网站修复 · 公网发布 2026-10-10

已提交、推送并部署至 <https://119.91.211.156>。冻结源码为 `a863b0e153069e3c4194c346f1a0be08b8f9be0d`，公网验收完成于 2026-10-10 15:27 Asia/Shanghai。此次发布不改变计算核的方法版本。

## 已发布内容

- CLI `readme` 命令和包内 `CLI_README.md`：用户配置的 AI 可离线读取单位、输入/结果契约、JSON/CSV 解释及计算限制。
- 诊断到实际输入的定位、当前选中阶段与上次运行检查的区分，保留草稿和旧报告。发布复核额外修正有效进水请求在「计算就绪」阶段列表中的显示遗漏。
- 项目 JSON 恢复：先做只读预览，再由用户确认名称，保存为当前工作区的新 UUID、修订 1；保留输入语义，不覆盖原项目，不恢复旧运行或自动计算。
- 窄屏总站导航、正文对比度、View Project 触控面积、元数据与 favicon；展板使用无损 WebP，只加载当前图；声音延后至实际允许的交互。
- Nginx 启用真实 JS/CSS gzip、严格缺失路径 404、正确 WAV/WOFF2 MIME 和静态缓存策略。保留既有已启用限流及手动主题选择。

功能和文档提交依次为 `7aa1b56`、`77a1ef8`、`3bd1a8e`、`4df8963`、`a863b0e`，已推送至 `origin/feature/plimsoll-1.0`。字体资产没有新增差异。

## 独立验收

- 前端最终全量：36 文件 **638/638**，构建 106 模块成功。
- 后端全量：**103 通过**，2 个 PostgreSQL 专项在独立临时实例中另跑并通过；1 条既有 Starlette/httpx 弃用提示。未拿 SQLite 跳过项冒充 PostgreSQL 验收。
- CLI、打包导入和 JSON/CSV：**48 通过、27 个子测试通过**。Windows 打包器 18 通过、1 个符号链接权限跳过；生产 Linux **19/19**，无跳过。
- 冻结包在服务器核对 **158 个文件**；候选镜像与运行镜像各核对 **100 个运行文件**。服务安装位置的 `main`、`projects`、`runs`、`worker` 与冻结源摘要相符。
- 公网可信 TLS 逐字节核对 **47 个静态资源**，共 6,016,876 字节，其中包含保留资源。保留上一版 **18 个哈希文件**；发布前打开的浏览器仍能加载旧工作空间模块并连接新后端。
- 当前四个 JS/CSS 包合计 722,270 字节，gzip 实际传输 197,921 字节，解压后与清单一致；这包含延后加载的工作空间包，不能称作全部首屏传输。
- 缺失普通路径、`/admin/`、音效、字体、展板及哈希资源均实际 404，未给缺失资源永久缓存；WAV、WOFF2、WebP 类型与缓存头通过复核。
- 原生浏览器 Work/About/Credits 在 **320、390、1440px** 下导航均完整且无横向溢出；新静音首屏仅请求 `ship-plan-01.webp`，不请求五个音效。大文件预览取消、BOM 文件预览、明确确认新名称、保存后编辑器打开通过公网浏览器操作。
- 公网 API 覆盖只读预览（含 2.7MB 型线）、数据准确保留、新身份与修订、源项目保留、归属隔离、无自动运行、计算报告/无效名称/CSRF 拒绝且无孤儿项目。另执行一个有界五阶段计算，JSON/CSV 导出及身份/方法核对通过。

## 数据与部署身份

切换前后的 **7 个项目、12 个修订、10 个运行**逐条摘要相同。验收明确新增 4 个自有测试项目与 1 次计算，最终为 11/16/11；原有记录的摘要再次逐条匹配，无活跃计算。数据库容器 ID 未改变，API 与 worker 使用候选镜像重建，三者重启计数均为 0。

- 发布目录：`/opt/plimsoll/releases/plimsoll-web-20261010T065436Z-a863b0e`
- 当前链接：`/opt/plimsoll/current` 指向上述目录。
- 发布包：`plimsoll-web-20261010T065436Z-a863b0e.tar.gz`
- 包 SHA256：`83f36daf2439a78b78e2f1d9ceae0e37a1313904e7b55c4bf9516f3d35839b14`
- 镜像：`plimsoll/runtime:workflow-a863b0e`，ID `sha256:52ffea938765e9fca217c3fb4ccbd74278e7386b3b8a227a35ad8dc26da9859c`；`plimsoll/runtime:local` 指向相同镜像。
- 数据库迁移仍为 `6226f03d283f (head)`；既有一次性 migrate 服务运行成功，无新增迁移文件。
- 发布前数据库备份：`/opt/plimsoll/backups/plimsoll-db-20261010T065533Z.dump`，3,947,474 字节，SHA256 `248cd3d73c78808c28c9f0ca583bb8f3e0a6718265c6f8c740fb72b8cac57465`。
- 实际 Nginx 站点：`/etc/nginx/sites-available/plimsoll`，原命名继续使用，`nginx -t` 通过。

运行版本继续为 `selected-loading-analysis-2`、`loaded-projected-equilibrium-2`、`connected-quasi-static-flooding-3`、`vented-orifice-network-2`、`selected-plane-resistance-adapter-2`。相比上版，运行源码仅变更 CLI 指南/命令及项目恢复后端，没有几何、稳定性、进水或阻力核改动。

## 回滚与证据

保留旧目录 `/opt/plimsoll/releases/plimsoll-web-20261009T163351Z-3a51f03`、镜像 `plimsoll/runtime:rollback-workflow-20261010` 和原配置 `/opt/plimsoll/backups/nginx-workflow-before-20261010-r2.conf`。回滚需一起恢复运行镜像、静态目录链接和同名 Nginx 站点；不运行 `down -v`，不回写旧数据库覆盖后续输入。具体步骤遵循[生产运维说明](../plimsoll-1.0/web-production-operations.md)。

第一次切换前，发布脚本将注释里的占位符示例误判为未替换配置，自动回滚；应用容器 ID、旧配置摘要和项目历史均未改变。修正检查后完成本次发布，原失败与回滚记录仍留存。

本地完整证据在任务输出目录 `C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/workflow-release-2026-10-10/`，包含冻结清单、独立测试日志、前后记录摘要、镜像探针、实际 gzip 大小、HTTP 检查、原生浏览器截图及最终 `acceptance.json`。运行中的后续收敛研究独立于本发布包，其本地结果不等同于已经部署的运行算法更新。
