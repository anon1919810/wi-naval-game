# 首页预览与工作空间反馈生产发布 · 2026-10-07

**已上线并完成公网验收。** 网站为 [https://119.91.211.156](https://119.91.211.156)，IP 直连、匿名工作空间，未绑定域名。此次发布第三组工作空间转场与加载反馈，以及首页字母蓝色预览、合成提示音、边缘放大镜。被用户否决的 520ms 展板覆片已完全撤回；Work/About 同步换入内容并保留既有 260ms 局部进入动画。下一版遮罩仍在讨论，不属于此次发布。

## 发布身份

| 项目 | 已验证值 |
| --- | --- |
| 源码 | `0add0b43a8595fa532f69ce7d55c68f688f1a2d9`（`0add0b4`） |
| 分支 | `feature/plimsoll-1.0`，已推送 origin |
| 发布名 | `plimsoll-web-20261006T161702Z-0add0b4`；时间戳为 UTC，交接日期按 Asia/Shanghai |
| 当前目录 | `/opt/plimsoll/releases/plimsoll-web-20261006T161702Z-0add0b4` |
| 上一目录 | `/opt/plimsoll/releases/plimsoll-web-20261006T032422Z-7131a78`，保留可回滚 |
| 归档字节数 | 2,074,045 |
| 归档 SHA256 | `13c361ead349553b88beef2bf1d1b9a5b146db2088271034307fc6b1e8a5cbd8` |
| 清单 | 131 个文件，合计 6,944,192 解压字节；每文件路径、字节数与 SHA256 均验证 |
| 源码冻结 | 归档从干净工作区生成，manifest 中 dirty=false、source_freeze_confirmed=true |
| 数据库备份 | `/opt/plimsoll/backups/plimsoll-db-20261006T154541Z.dump`，既有备份服务执行成功 |

部署后文档提交不改变以上发布源码身份。前端产物保留上一版本 6 个哈希资源，避免已打开页面后续加载旧 chunk 时出现 404；它们亦纳入发布清单。

## 发布与验证

Codex 独立验收：全量前端 **24 文件 393/393** 通过，TypeScript/Vite 构建成功，`git diff --check` 通过。首页功能簇 **6 文件 125/125**；本地桌面 1440×960 与 1024×900、浅深主题、reduced-motion、反向预览与实际双向换页通过，详见 [首页交接](homepage-motion-2026-10-06.md)。8 个既有工作空间/全局样式保护文件与 7 个字体文件哈希保持一致。部署包装测试在 Windows 为 17 通过、1 项 symlink 权限跳过，服务器 Linux **18/18** 通过。

服务器先校验归档和全部 131 个文件；所有非前端 dist 的运行时、计算核心、后端与部署文件，与上一发布逐字节一致。`nginx -t` 成功后原子切换 `/opt/plimsoll/current`，未重建或重启容器、未执行迁移、未修改配置；API、worker、db 容器 ID 和 restart count 与切换前一致，均为 0 次重启。切换后本机 API 与可信 HTTPS 首页检查成功。

公网通过系统 TLS 校验获取 **22 个静态文件**，状态码、字节数和 SHA256 均与发布清单一致；index Cache-Control 包含 no-cache，API health 为 ok。

真实生产浏览器刷新后验收：

- 新 Preview sound 控件和双层字母导航可见；About 立即出现在 `data-ff-page=in` 阶段，之后该属性释放，页面中无 `.ff-cover`。双向导航正常。
- 开启 Inspect 后，圆心移动至展板左边缘内 1px：展板左坐标 22.25，圆心 23.25，圆框左坐标 -76.75、直径 200；十字仍在指针位置，12 道中性刻度存在。复位 Inspect Off。
- 读取现有“公网验收 · 通用试验船”：修订仍为 2，船长 92 m；打开已有运行 `90e0e7d9-142e-4a30-a024-67c17468e0fa` 和完整报告，8 个请求阶段可读，质量 4700 t、水线高度 5.490461 m；GM、未请求功率与续航继续保持未知。
- 本轮没有创建工作空间、项目、修订或运行，没有修改工程输入、没有保存或启动计算；复用既有浏览器身份。未切换生产主题，最终返回浅色 Work 主页、Inspect Off、默认视口。刷新后的 warn/error 控制台记录为空。

本轮浏览器验证不包含生产故障注入、音色听感评审或原生打印对话框；这些不由静态资源校验代替。移动端仍不在范围内。

本地证据位于当前任务工作目录 `C:/Users/杨睿/Documents/Codex/2026-10-05/y-s-formfield-plimsoll-ui-c/outputs/`：

- `plimsoll-web-20261006T161702Z-0add0b4.manifest.json`
- `public-ui-release-2026-10-07.json`
- `production-home-2026-10-07.png`
- `production-workspace-2026-10-07.png`
- `production-report-2026-10-07.png`

## 静态回滚

保留前后两个发布目录与数据库备份。需要撤销本次 UI 时，在服务器执行下列静态链接切换，不需要重启容器或迁移数据库：

```bash
set -euo pipefail
target=/opt/plimsoll/releases/plimsoll-web-20261006T032422Z-7131a78
test -f "$target/web/frontend/dist/index.html"
nginx -t
ln -s "$target" /opt/plimsoll/current.rollback
mv -Tf /opt/plimsoll/current.rollback /opt/plimsoll/current
readlink -f /opt/plimsoll/current
curl -fsS https://119.91.211.156/index.html
curl -fsS http://127.0.0.1:18000/api/health
```

[上一生产交接](release-2026-10-06.md) · [工作空间反馈交接](transition-loading-2026-10-06.md) · [首页交接](homepage-motion-2026-10-06.md) · [生产运维手册](../plimsoll-1.0/web-production-operations.md)
