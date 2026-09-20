# Queen Mary 损伤试验场 v1

## 打开

Unity 工程 `D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval`，打开 `Assets/Scenes/DamageRange.unity`。场景现在会在编辑器中生成可见的剖段预览；需要左侧参数面板、炮弹回放和 JSON 导出时再点击 Play。场景为独立试验，不替换 GameplayLab。也可通过 `Tools → Naval → Open damage range` 打开现有场景，或用 `Tools → Naval → Build damage range` 重新生成并保存场景。
项目编辑器启动时会尝试把这个场景带到前台；若当前会话仍停在其他场景，执行一次 `Tools → Naval → Open damage range` 即可切换。

左侧调整三层板厚、材料阻力系数、撞击速度、入射角、参考穿深预算、引信（接触／延迟／哑弹）、延时、破片预算和爆炸作用系数。修改后点击 FIRE。右键拖动旋转视角；空格暂停；右侧切换剖视和破片路径，拖动回放进度或逐事件观察。右侧数值和路径展示完整的预计算结果，回放动画仅解释时间顺序，不是实时求解器。

Baseline 恢复默认；Thick plate 演示厚板阻挡哑弹；Open walls 将三层阻力设为零。Repeat shot 使用同一随机种子，Next seed 只调整随机种子，随后 FIRE。

EXPORT SHOT JSON 保存参数、事件、破片轨迹及三个模块的损伤分量。LOAD LAST SHOT 重新计算上次导出的参数并比较结果。默认输出到 Unity `Application.persistentDataPath/DamageRange`，界面显示完整位置；命令行 `-labOutput <目录>` 可覆盖。

## 计算模型和边界

本版是通用舰体剖段的可解释计算样板，尺寸和设备布置不声称是 Queen Mary 某个真实舱段。三个模块为 Boiler_Room_1、Engine_Room_1 和 Feed_Pump；其中 Feed_Pump 是实验新增 ID，尚未绑定主游戏契约。

- 飞行：短距离直线、事件驱动；在交点间按当前速度推进时间，无重力、阻力、完整远程弹道。
- 穿透：以 600 m/s 的参考毫米预算乘速度平方比例；每层扣除 `板厚 × 材料系数 / max(abs(方向法向分量), 0.05)`。剩余速度按剩余预算的平方根变化。这是明确的实验阻力代理，不是经史料校准的穿甲公式。各层各扣一次。
- 装甲是有限的 8 × 14 m 平面。板厚参与阻力，但不计算穿板时间、变形或裂纹；视觉板厚至少 40 mm 以便观察。外壳、屋顶、支架等装饰不参与阻力计算。
- 引信：首次与配置平面相交即触发，包括零阻力平面；接触立即起爆，延迟引信按时间起爆，哑弹不爆。停弹后已启动的引信继续计时。炮弹离开 x=13 m 的试验边界后终止追踪，不结算舱外后续起爆。没有引信保险、真实触发阈值或弹种认证。
- 模块：射线路径穿过设备盒时增加固定直接损伤；设备本体暂不扣除弹丸速度。事件会明确记录这一近似。
- 爆炸：使用无量纲的距离衰减和舱壁透过系数，不表示真实压力或冲量；没有密闭舱压力反射、开口传播、火灾或进水模型。
- 破片：默认 192 条固定种子的等权球面轨迹，每条可被板阻挡或消耗预算，首个设备吸收该样本。总样本权重为 1。显示最多约 96 条轨迹，显示开关不改变损伤。权重归一不等于采样误差消失，也不保证不同采样数结果完全相同。
- 总损伤为直接、爆炸、破片代理值之和，限制为 0–1；0.15 起受损，0.75 起失能。这些阈值是演示配置。
- 未实现装甲崩落、跳弹、连续破口、结构断裂、碎片刚体碰撞、真实爆炸物或完整舰船战斗接入。

## 验证入口

源码位于 `unity/Scripts/DamageRangeModel.cs`、`DamageRangeView.cs`，场景生成器为 `unity/Editor/DamageRangeBuilder.cs`，Unity NUnit 测试为 `unity/Tests/EditMode/DamageRangeTests.cs`。

`BuildBatch` 可用 `-executeMethod Naval.EditorTools.DamageRangeBuilder.BuildBatch -labOutput <结果目录>` 构建单独播放器，并写出 baseline.json 和 200 次求解平均耗时。求解计时包含完整诊断报告分配，不代表 GPU 时间或游戏 FPS。

Unity Test Runner 中运行 DamageRangeTests。是否实际通过，以本次 XML 为准；独立程序集编译不能替代编辑器导入、渲染与播放器验收。
