# Research brief — HMS Queen Mary v3 模型精修 + LOD 阈值补全

## Question

在**不引入未经考证的史实断言**、型线仍可能缺图的前提下：

1. 1913 年服役外观的 HMS Queen Mary，在 **50–200 m 中距观察 / 同屏 15 艘** 的游戏灰盒标准下，哪些**可程序化精修的视觉点**最值得改（轮廓、桅杆/烟囱/炮塔/炮廓/上层建筑/识别特征）？
2. 同类拟真向海战/舰队游戏（或 Unity 多舰场景）在 **LOD 屏幕高度阈值、lodBias、编队纵深 vs 相机距离** 上有什么可引用的实践，用来替换当前默认 `0.20/0.08/0.03/0.01`？

## Scope

**In**
- 史实视觉点：RMG/Wikipedia/naval encyclopedia/WW1 资料中与 1913 原状相关、且可转化为灰盒几何或数据字段的内容
- 观察距离与 LOD：Unity LODGroup 文档、屏幕高度比例公式、舰队/海战游戏公开实践
- 可验收产物：精修点清单（带 source 或 estimate 标签）、LOD 阈值建议区间与推导输入（相机 FOV、船长、距离、lodBias）

**Out**
- 型线数字重构（缺正式图纸时不做）
- 多人联机、完整损管、弹道穿深系统
- 把 1916 或战时配置当成 1913 证据
- 贴图/PBR 写实化（当前约定是程序化灰盒）

## Assumptions
- 资产仓库：`C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17`，当前版本 `queen_mary_v3`
- 目标状态：1913 服役原状；`historically_certified` 保持 false，除非另有考证
- 观察规划：50–200 m，同屏约 15 艘；Unity 2022.3 URP；舰长 213.4 m
- 当前 LOD 阈值是默认值；复核已指出 automatic 档在现基准相机下不会跨档
- 用户同时要求：「美化建模/精修」+「补全 LOD 阈值等内容」
- 深度：**standard**；今日日期：**2026-09-18**

## Angles

- **F1** — Queen Mary (1912) / 1913 服役原状：可核验的识别特征与常见误配（桅杆、烟囱、炮廓、舰艉步廊、炮塔布局）
- **F2** — 中距 50–200 m 灰盒：战舰模型哪些视觉层次真正影响可读性/识别，哪些可以进远档丢弃
- **F3** — Unity LODGroup 屏幕高度阈值与 lodBias：官方/社区推荐、公式边界、多船场景常见坑
- **F4** — 舰队/海战类游戏或引擎示例：LOD 档位设计、自动切换距离、性能取舍的公开资料

## Decision this research feeds

Compose-Next feature：模型精修（Blender `queen_mary.py` 可见几何/装饰，仍标 estimate）+ Unity LOD 阈值/配置补全（`ShipLodBuilder`、契约/定义字段、验收与文档），使自动档在目标相机下**可观测地**跨档，并保留炮塔链独立变换等硬约束。
