# 阅读刻度、滚动图案与标题入口发布 · 2026-10-07

**已推送、已部署并完成公网复核。** [网站](https://119.91.211.156/#/work) · [Plimsoll 详情](https://119.91.211.156/#/work/plimsoll)。日期按 Asia/Shanghai；发布包名称的时间戳为 UTC。

## 发布内容

- Work 和详情页的 Plimsoll 标题整合工具入口，圆形蓝字预览、红色 i 点、同步下划线和快速反向接续；Work 的 View Project 随悬浮或焦点展开。
- 页眉采用声音、手动主题与重播图标，移除 SYSTEM 主题跟随及底部重复出口。
- 详情章节标题停驻；About 和详情页阅读刻度支持章节定位、当前标记、目标焦点和有条件的轻提示声。
- Work 尺规弧线及 About 参数曲线、尺度、摩擦系数与功率研究随原生滚动有界变化，支持隐藏页面和 reduced-motion 静态回退。
- 本次没有新增依赖、改动全局字体资产、工作空间、后端或移动端设计。致谢页的文案仍在讨论，不在此包中。

## 发布身份

| 项目 | 核实值 |
| --- | --- |
| 源码提交 | `c20e22ce1af0b661ab6326e3876a96d7afe04be9` |
| 分支 | `feature/plimsoll-1.0`，已推送 origin |
| 发布名 | `plimsoll-web-20261007T082029Z-c20e22c` |
| 当前目录 | `/opt/plimsoll/releases/plimsoll-web-20261007T082029Z-c20e22c` |
| 上一目录 | `/opt/plimsoll/releases/plimsoll-web-20261006T195253Z-cec19c9` |
| 归档大小 | 2,509,933 字节 |
| 归档 SHA256 | `7347808ccd02e5ffdcb68b0d11d0cda2cd8cf1a13addb3d0240fa5a278cb4136` |
| 清单 | 139 个文件，解包共 8,349,426 字节；逐一核对大小及 SHA256 |
| 源码冻结 | 干净提交，dirty=false、source_freeze_confirmed=true |

产物保留上一发布的 12 个哈希资源，支持已打开页面继续加载旧文件。服务器逐字节核对非 dist 文件与上一版相同后，原子切换 current；没有重启容器、执行数据库迁移或更改配置。api / worker / db 容器 ID 均不变，重启计数均为 0。`nginx -t`、服务器本机 API 和公网 API health 均通过。

## 验收证据

- Codex 发布前重新独立运行完整前端：**28 文件、496/496，无跳过**；TypeScript/Vite 构建 **95 模块**通过。暂存差异与工作树空白检查通过。
- 打包器：Windows **17 通过、1 项符号链接权限跳过**；服务器 Linux **18/18** 通过。
- 公网可信 HTTPS 校验 **30 个静态文件**，字节数与 SHA256 全部匹配发布清单；index 缓存策略含 no-cache，API health=ok。
- 真实生产浏览器加载 `index-CZatUM9V.js`。1280×720 下，标题蓝字、红色 i 点、下划线与展开 View Project 可见；点击可进入详情。Capabilities 刻度可跳转、更新当前标记并聚焦章节标题，没有横向溢出。
- 点击详情标题进入生产工作空间，读取既有“公网验收 · 通用试验船”（修订 2）项目库条目成功；返回原详情后焦点恢复至 Open Plimsoll。未创建项目、保存修订或启动计算。
- 1440/1280/1024 桌面、浅深主题、动态 reduced-motion、图案游标和停驻的本地细项见 [独立验收交接](scroll-acceptance-2026-10-07.md)。没有扩大为移动端、生产故障注入或音色听感验收。

证据保存在当前 Codex 任务目录 `outputs/`：`scroll-release-tests.log`、`scroll-deployment-2026-10-07.log`、`public-scroll-release-2026-10-07.json`、同名发布 manifest、`production-scroll-work-2026-10-07.png`、`production-scroll-reading-2026-10-07.png`、`production-scroll-workspace-2026-10-07.png`。

## 静态回滚

上一发布目录保留。需要回滚时，在服务器运行：

```bash
set -euo pipefail
target=/opt/plimsoll/releases/plimsoll-web-20261006T195253Z-cec19c9
test -f "$target/web/frontend/dist/index.html"
nginx -t
ln -s "$target" /opt/plimsoll/current.rollback
mv -Tf /opt/plimsoll/current.rollback /opt/plimsoll/current
readlink -f /opt/plimsoll/current
curl -fsS https://119.91.211.156/index.html
curl -fsS http://127.0.0.1:18000/api/health
```

[上一生产发布](release-layout-2026-10-07.md) · [实施与验收](scroll-acceptance-2026-10-07.md)
