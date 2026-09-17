# HMS Queen Mary — v3 早期照片精修

以桌面 DeepSeek v2 为基线继续精修，保留原有 98 个对象的名称与父子层级。旧版 `queen_mary` 文件夹保持不变，本目录 `queen_mary_v3` 是此次成果。

## 本次改变

- 按最新确认，把两座三脚桅改为早期单杆桅、横桁与拉索；前桅观察平台、后桅吊杆为照片解释。
- 主炮采用收束炮管、实际内凹炮口、独立炮管轴心和软化边缘；炮座与旋转/俯仰结构保持分离。
- 16 个副炮炮廓有实际凹口；3 个烟囱有内壁、开口、环箍和格栅，中烟囱维持圆形。
- 补充舰桥窗、甲板栏杆、舷窗、4 艘艇、锚机简形和舰艉阳台罩棚。
- 船壳平滑着色，修复型值截面生成时遗漏右舷平板龙骨端点的问题；型值表及其插值接口保持不变。
- 水下轴系与支架仍是估算外观，用简化几何改善连接。没有增加高模、贴图或雕刻。

## 交付和打开

| 文件 | 用途 |
|---|---|
| `HMS_Queen_Mary_1913_Refined_v3.blend` | 完整场景，内嵌生成脚本 |
| `HMS_Queen_Mary_1913_Refined_v3.fbx` | Unity 导入资产，不含预览相机 |
| `queen_mary.py` | 自包含 bpy 生成器；重新运行会清空场景 |
| `rebuild.ps1` | 构建、重复生成检查、Blender 检查、FBX 回读检查 |
| `object_manifest.json` / `objects.csv` / `created_objects.txt` | 名称、角色、层级、原点、尺寸、包围盒 |
| `verification.json` / `fbx_verification.json` | 本次几何与导出验证 |
| `unity_verification.json` | 本次实际 Unity 导入结果，包含 FBX SHA256 |
| `integration_verification.json` | 与 DeepSeek 基线的对象、层级和文件哈希对照 |
| `firing_arcs.json` | 几何扫描得到的近似射界，见下方限制 |
| `参考素材/` | 原始参考图及使用说明 |
| `docs/` | 原交接文件，仅作历史记录，冲突处以本说明及实际报告为准 |

在本目录 PowerShell 中执行 `./rebuild.ps1`。支持 `-SkipRender` 和 `-BlenderExe '完整路径'`。
Microsoft Store 的 Blender 启动器可能没有标准输出；脚本检查本轮完成记录及文件时间，不能仅看退出码或旧 FBX 是否存在。
GUI 使用 Scripting → Text Editor 打开脚本后 Run Script；造型修改必须写入脚本才可保留。
本次实际使用 Blender **4.5.14 LTS**；使用 3.x/4.x 共用接口，未逐一运行所有版本。

预览：`Overview.png` 整体、`Starboard.png` 右舷、`Top.png` 俯视、`Bow.png` 舰艏、`Stern_Detail.png`/`Stern_Aft.png` 艉部；`Detail_50m.png` 为距右舷约 50 米的透视，`Whole_200m.png` 为距中心约 200 米的透视。距离是当前精修质量参照，不是 LOD 切换规则。

## 尺度、系统和性能边界

1 Blender 单位 = 1 米；X 右舷、Y 船头、Z 向上；水线 Z=0，龙骨 −9.9，船壳主甲板 +5.1。船壳包围盒为 27.2 × 213.4 × 15.0 米；带舷弧的艏楼另计。

保留 `OFFSETS`、`station_params()`、`halfbeam_at()`、`deck_halfbeam()`，支持把 `hull_offsets.json` 放在脚本旁覆盖内置型值。格式为 `{"sources":"...","stations":[[y,deck_halfbeam,waterline_halfbeam,keel_z,flat_keel_halfbeam],...]}`。内置站位仍是估算，不是测绘型线。

实际清单：**101 个资产对象、85 个网格、31,164 个三角面**；另有 8 个仅用于预览的相机。保留 4 个弹药库、7 个锅炉舱、2 个轮机舱、1 个操舵舱，共 **14 个损伤体量**；另有 **8 件装甲网格**，并非原交接文档所写的 10 件。

扣除内部 22 个网格，外部有 63 个网格。新增的三件合并装饰为 `Deck_Visual_Details`、`Deck_Fittings`、`Rigging_Stays`。战斗相关的炮塔、俯仰轴、炮管和副炮仍独立。
这只是对象预算检查，不能代表 10–30 艘舰的实际帧率。多材质会增加绘制批次；LOD、图标切换、GPU/CPU 性能测试尚未实施。

## 验证结果及 Unity 约定

32 项阻断性几何检查、18 项 FBX 回读检查通过；另记录 13 项史实/配置假设，它们的通过表示与当前参数一致，不表示史实认证。同场景重复生成几何哈希一致。

Unity **2022.3.62f3c1** 在独立验证工程中实际导入最终 FBX：检查 101 个模块的名称/层级、85 个网格、1:1 船体尺寸、舰艏方向和四座炮塔的旋转/俯仰，结果通过。没有改动 `ThinkingFactory`。

导入使用 Scale Factor=1、Use File Scale=false、Bake Axis Conversion=false、Preserve Hierarchy=true，不导入相机和灯光。Unity 世界尺寸应为 X 27.2 × Y 15.0 × Z 213.4 米，船头 +Z，龙骨 Y≈−9.9。
按最新 DeepSeek 管线，FBX 导出时绕 Blender Z 旋转 180°，导出后恢复源场景，因此源 .blend 仍然舰艏 +Y。本次 Unity 实测舰艏 +Z 且物理右舷 +X；请勿混用早期导入方式。保留内部导入旋转，在外层加游戏控制根节点。相对初始局部旋转控制：

```csharp
turret.localRotation = restYaw * Quaternion.AngleAxis(yawDeg, Vector3.forward);
elevation.localRotation = restPitch * Quaternion.AngleAxis(elevationDeg, Vector3.right);
```

Q/X 的 yawDeg 相对于各自朝艉的初始方向。更改导入轴转换设置后须重新验轴。当前验证为读取顶点启用了 Read/Write；正式游戏可按需要关闭。
URP 的 Lit 灰色材质需在工程中绑定，本次没有验证 URP 场景渲染。内部损伤/装甲体量要关闭 Renderer 并按需求配置碰撞层，FBX 不自动建立游戏碰撞器。

复核工具在 `unity/Editor/QueenMaryImportCheck.cs`：放入独立 Unity 工程的 `Assets/Editor`；将 FBX 复制为 `Assets/QueenMary.fbx`，将清单复制为 `Assets/QueenMaryManifest.json`，将 `ship_contract.unity.json` 复制为 `Assets/QueenMaryContract.json`，并把 `unity/Scripts/ShipContract.cs` 放入 Assets 下。用 `-batchmode -nographics -projectPath <工程> -executeMethod QueenMaryImportCheck.Run` 启动。默认报告写到工程根 `QueenMary_UnityVerification.json`，可加 `-queenMaryReport <绝对路径>`。

## 史实与近似数据

舱室体积、装甲覆盖范围、副炮精确站位、桅杆尺寸和艉部水下结构仍为估算。参考图含不同日期和舰名尚未核实的照片，未混用为确定史实。
保留 DeepSeek 舰船数据；其中满载排水量 32,160 t 与最初需求的 32,158 t 存在取整差异，后续数据校准需要统一来源，本轮未擅自改动系统数据。

`firing_arcs.json` 每 5° 扫描，只对左炮管中心线离散取样并对静态包围盒检查，使用 0.30 m 阈值；其他炮塔/炮管按静止姿态参与，自身炮座被忽略，细拉索与栏杆未参与。没有检查连续扫掠、两根炮管完整体积、动态炮塔组合、弹道或炮口冲击。原报告“排除所有主炮塔/炮座/炮管”的说明与算法不一致，已更正说明。此文件不能直接当作历史射界或最终游戏开火许可。


## 最新 DeepSeek 补充的接续

最终合入的是桌面 21:27 修改的最新生成器，不是早期工作备份。保留新版本的轮机舱避重叠调整、系统关联、命中区、浮力舱容、材质单一数据源，以及下列五份随模型生成的数据：

- `damage_model.json`：弹药库/炮塔、锅炉/轮机/轴系、烟囱、操舵与火控系统关联。
- `hydrostatics.json`：型值表积分的排水体积、水线面、浮心。
- `buoyancy_compartments.json`：14 个估算舱室的体积与渗透率。
- `ship_contract.json` / `ship_contract.unity.json`：完整契约及 JsonUtility 可读取的数组形式，FBX 文件名指向 v3。

另外修正水线面 Simpson 积分中点宽度少乘 2 的错误，水线面面积为 4610.4 m²；这是估算型值表的数值结果，不是历史测量。排水体积约 30663.7 m³，对应 31430.3 t，较继承的满载数据低 2.27%，不构成完整静水力/稳性认证。
Unity 已使用桌面现有 `Naval.ShipContractData` 类型实际解析新契约，核对四座炮塔、16 门副炮、6 种材质与全部模块名称。
轴向由四座炮塔的正负本地轴逐一运动探测：本次正确命令为 **本地 +Z 偏航、本地 +X 俯仰，正角度**。不要继续套用早期 README 的负号；以当前报告 `turretAxes` 为准。

桌面旧 `unity_integration/sync_to_unity.ps1` 默认读取兄弟目录 `queen_mary` 和 `_Greybox.fbx`。它仍保留原样；接入 v3 时应改为读取本目录及契约中的新 FBX 文件名，或手动复制到独立海战工程。当前没有部署 URP 场景或替换用户工程。

复核工程需包含 Unity 内置 `com.unity.modules.jsonserialize` 模块，供运行时 ShipContractData 使用 JsonUtility；空工程若裁掉了此模块，先在 Packages/manifest.json 恢复它。
