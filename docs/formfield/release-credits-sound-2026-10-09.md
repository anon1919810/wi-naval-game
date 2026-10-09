# Credits 与共用交互音效发布 · 2026-10-09

**已推送、已部署并完成公网复核。** [网站](https://119.91.211.156/#/work) · [Credits](https://119.91.211.156/#/credits) · [Plimsoll](https://119.91.211.156/#/plimsoll)。日期按 Asia/Shanghai，发布包名称的时间戳为 UTC。

## 发布内容

- Credits 与 Work / About 同级，三个导航使用相同字号；Credits 预览时 i 点为瑞士红，字干为蓝色，保留鼠标进入处扩散、同步下划线和快速反向接续。
- 致谢 simppleasedie 的艺术设计和视觉风格建议、Suxx 的 Coding Plan 支持。规划与设计方向署名 Yang Duanming，审查署名 Codex / DSH / Kimi Code，实现辅助署名 OpenCode；来源和字体说明使用英文。
- 总站和工作空间共用 Touch / Detent / Passage A / Resolve / Hold。Passage 为用户确认的 180ms 无明显音调滤波噪声；五个 WAV 与试听版本逐字节相同。
- 音效开关与静音偏好在总站和工作空间之间共用；首次真实手势解锁，连续输入、滚动和放大镜移动保持安静。保存和运行等反馈遵循真实结果和现有请求生命周期。
- 源码另含本地启动器修复（`9e3f946`），复用已有数据库；启动器不在生产发布包内。现有 Space Grotesk / Inter 与此前桌面滚动和转场设计继续保留。

## 发布身份

| 项目 | 核实值 |
| --- | --- |
| 源码提交 | `1c33865dd1ffedf3bfe3e9d066c71c77af2fcbf5` |
| 源码树 | `6a17c5050dee462b128fd371242ae50ace1059c9` |
| 分支 | `feature/plimsoll-1.0`，已推送 origin |
| 发布名 | `plimsoll-web-20261009T111457Z-1c33865` |
| 当前目录 | `/opt/plimsoll/releases/plimsoll-web-20261009T111457Z-1c33865` |
| 上一目录 | `/opt/plimsoll/releases/plimsoll-web-20261007T082029Z-c20e22c` |
| 归档大小 | 2,756,209 字节 |
| 归档 SHA256 | `e5694bbddd0471f855148de042ef5108706036eacfad2705842bfce7ba3c2109` |
| 清单 | 148 个文件，解包共 9,117,528 字节；全部核对大小与 SHA256 |
| 源码冻结 | 干净提交，dirty=false、source_freeze_confirmed=true |

服务器确认 109 个非 dist 文件与旧版一致，并保留上一版的 15 个哈希资源，随后原子切换 `/opt/plimsoll/current`。未重建或重启服务，未迁移数据库或修改配置。API / worker / db 容器 ID 均与发布前一致，重启计数均为 0；`nginx -t`、本机 API 和公网 API health 均通过。

## 验收证据

- 发布源码的最终独立验收：前端 **30 文件、534/534，无跳过**（`--maxWorkers=2`），TypeScript/Vite 构建 **100 模块**通过。发布仅增加回滚兼容的旧哈希资源，未修改或重建已验收源码。
- 发布打包器：Windows **17 通过、1 项符号链接权限跳过**；生产 Linux **18/18，无跳过**。
- 从本机通过可信 HTTPS 逐个获取 **39 个静态文件**，字节数与 SHA256 全部匹配清单，包括新入口、工具懒加载包、五个已认可音频及旧资源。公开 index 的缓存策略为 `no-cache`，API health=ok。
- 真实公网浏览器加载 Credits，致谢内容正确；Work / About / Credits 计算字号均为 96.14px。Credits 预览的蓝色字干与红色 i 点可见，底线同步伸展。
- 真实手势后观察到 `AudioBufferSource`；静音设置从总站同步到工作空间，恢复开启后返回总站及刷新保持开启。公开页控制台未捕获错误。此项证明接入和播放路径，没有重新声称一次主观听感验收。
- 进入 Plimsoll 可读取既有“公网验收 · 通用试验船”（修订 2）及匹配的已保存结果；保存按钮保持禁用，草稿与保存修订一致。未创建项目、保存修订或启动计算。
- 本轮维持桌面范围，未扩大为移动端或生产失败注入。完整实现细项见 [Credits 验收](credits-2026-10-08.md)和[音效接入记录](interaction-sound-integration-2026-10-09.md)。

证据保存在当前 Codex 任务目录 `outputs/`：`sound-push-tests-2026-10-09.log`、`sound-push-build-2026-10-09.log`、`formfield-public-20261009-artifact.json`、`formfield-public-20261009-before.json`、`formfield-public-20261009-deployment.log`、`formfield-public-20261009-deployed.json`、`formfield-public-20261009-assets.json`、`public-ui-release-2026-10-09.json`、`production-credits-2026-10-09.png`、`production-credits-preview-2026-10-09.png`、`production-workspace-2026-10-09.png`。归档与 manifest 保存在仓库的 `.superpowers/releases/`。

## 静态回滚

上一发布目录保留。需要回滚时，在服务器运行：

```bash
set -euo pipefail
target=/opt/plimsoll/releases/plimsoll-web-20261007T082029Z-c20e22c
test -f "$target/web/frontend/dist/index.html"
test ! -e /opt/plimsoll/current.rollback-20261009
test ! -L /opt/plimsoll/current.rollback-20261009
nginx -t
ln -s "$target" /opt/plimsoll/current.rollback-20261009
mv -Tf /opt/plimsoll/current.rollback-20261009 /opt/plimsoll/current
readlink -f /opt/plimsoll/current
curl -fsS https://119.91.211.156/index.html
curl -fsS http://127.0.0.1:18000/api/health
```

[上一生产发布](release-scroll-2026-10-07.md) · [音效接入](interaction-sound-integration-2026-10-09.md)
