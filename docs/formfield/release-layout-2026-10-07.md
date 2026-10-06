# 制图背景、圆形揭页与详情阅读排版发布 · 2026-10-07

**已推送、已部署并完成公网复核。** [网站](https://119.91.211.156) · [Plimsoll 详情](https://119.91.211.156/#/work/plimsoll)。日期按 Asia/Shanghai；发布包名称的时间戳为 UTC。

## 发布内容

- Work/About 的 500ms 圆形揭页、中性边界与衰减波纹；导航蓝色预览、Work 编号红色预览与合成提示音。
- Work 的大幅偏心尺规弧线；About 的参数曲线、三节舰船公式研究和十二列排版，撤下手写标语。
- 详情页保留左侧章节标题，右侧 27 个条目统一为标签在上、说明另起一行；标签 15px、正文 18–20px，占满右侧八列并左对齐。报告截图与图注撤下，保留展台所选船舶参考图；修复 Work 装饰误挂到长详情页的问题。
- 原有 Space Grotesk / Inter 字体、全局样式与工作空间保护文件共 15 个，哈希未变。Caveat 字体及许可证作为早期迭代资产保留，当前页面未加载该字体。

## 发布身份

| 项目 | 核实值 |
| --- | --- |
| 源码提交 | `cec19c93f9c2b85f0ad817711ed485b5b33aad5a` |
| 分支 | `feature/plimsoll-1.0`，已推送 origin |
| 发布名 | `plimsoll-web-20261006T195253Z-cec19c9` |
| 当前目录 | `/opt/plimsoll/releases/plimsoll-web-20261006T195253Z-cec19c9` |
| 上一目录 | `/opt/plimsoll/releases/plimsoll-web-20261006T161702Z-0add0b4` |
| 归档大小 | 2,327,348 字节 |
| 归档 SHA256 | `182db5cb4142f791bd4d763748d554c623b7985a8f6b489e49f77f9737f9eba9` |
| 清单 | 136 个文件，解包共 7,677,611 字节；所有文件哈希逐一通过 |
| 源码冻结 | 干净提交，dirty=false、source_freeze_confirmed=true |

前端产物保留上一发布的 9 个哈希资源，支持已打开页面继续加载旧资源。服务器核对非 dist 的计算核心、后端与部署文件和上一版逐字节相同后，原子切换 `current`。未重启容器、迁移数据库或改动配置；api / worker / db 的容器 ID 不变，重启计数均为 0。`nginx -t` 和本机 API 健康检查通过。本次不涉及数据库变更，未额外触发数据库备份；既有备份流程保持。

## 验收证据

- Codex 独立全量前端 **25 文件 427/427**，无跳过；TypeScript/Vite 构建通过，89 模块。暂存差异与最终工作树空白检查通过。
- 打包器 Windows **17 通过、1 项符号链接权限跳过**；服务器 Linux **18/18** 全部通过。
- 本地 1440/1280/1024 桌面，所有详情条目上下排列并占满右侧宽度，列线偏差小于 0.01px，无横向溢出；1024 深色阅读区通过。
- 公网可信 HTTPS 校验 **27 个静态文件**，字节数与 SHA256 全部匹配清单；首页缓存策略含 no-cache，API health=ok。
- 真实生产浏览器：新版详情脚本 `index-5yj6JDE2.js`，1440 视口正文实测 18.525px、标签 15px，27 条全部上下排列，报告图片不存在。About 新图形与公式、返回总站导航可读。
- 从 OPEN PLIMSOLL 进入原浏览器工作空间成功，读取既有“公网验收 · 通用试验船”（修订 2）。既有报告 `90e0e7d9-142e-4a30-a024-67c17468e0fa` 正常读取：8 个请求阶段，质量 4700 t，水线高度 5.490461 m；GM、功率工作点与续航保持未知。没有创建项目、保存修订或启动新计算。

证据在当前任务 `outputs/`：`public-layout-release-2026-10-07.json`、同名发布 manifest、`production-detail-stacked-2026-10-07.png`、`production-workspace-layout-release-2026-10-07.png`、`production-report-layout-release-2026-10-07.png`。未开展移动端、生产故障注入、音色听感或原生打印对话框验收。

## 静态回滚

上一发布目录保留。需要回滚时，在服务器运行：

```bash
set -euo pipefail
target=/opt/plimsoll/releases/plimsoll-web-20261006T161702Z-0add0b4
test -f "$target/web/frontend/dist/index.html"
nginx -t
ln -s "$target" /opt/plimsoll/current.rollback
mv -Tf /opt/plimsoll/current.rollback /opt/plimsoll/current
readlink -f /opt/plimsoll/current
curl -fsS https://119.91.211.156/index.html
curl -fsS http://127.0.0.1:18000/api/health
```

[上一生产发布](release-feedback-2026-10-07.md) · [设计与动效交接](circular-reveal-2026-10-07.md)
