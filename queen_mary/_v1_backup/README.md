# HMS Queen Mary — 灰盒标杆舰 v1

本资产用于一战海战游戏的第一阶段：验证舰体比例、关键布局、炮塔枢轴、稳定命名和 Unity 导入。它是按用户确认方案制作的灰盒，不是经过舰体线型、装甲或 1913 年装备考证的精确复原。

## 打开和重建

- `HMS_Queen_Mary_1913_Greybox.blend`：Blender 源场景，内嵌完整 `queen_mary.py` 文本。
- `HMS_Queen_Mary_1913_Greybox.fbx`：供 Unity 导入，保留 169 个语义对象，其中 150 个网格、6,232 个三角面；不含预览相机。
- `queen_mary.py`：自包含生成脚本，仅使用 Blender 自带的 bpy、bmesh、mathutils 和 Python 标准库。
- `rebuild.ps1`：重建并验收，检查输出时间戳和完成记录，避免 Store 启动器静默失效被误判为成功。
- `Overview.png`、`Starboard.png`、`Top.png`、`Bow.png`、`Stern_Detail.png`：直接由 Blender 渲染的五个视角。侧视与俯视图的船头在右侧。
- `object_manifest.json`、`objects.csv`、`created_objects.txt`：对象角色、父子关系、原点、尺寸和世界包围盒。空对象的几何尺寸为零，不代表舱室体积。

在本文件夹打开 PowerShell：

```powershell
.\rebuild.ps1
```

可以用 `-BlenderExe '完整路径/blender.exe'` 指定另一套 Blender。`-SkipRender` 只更新模型与清单，保留旧预览图，因此造型调整后应完整重建。

也可以直接运行：

```powershell
& "$env:LOCALAPPDATA/Microsoft/WindowsApps/blender-launcher.exe" --background --factory-startup --python-exit-code 1 --python "$PWD/queen_mary.py" -- --out "$PWD" --check-repeat
```

GUI 用法：打开 `.blend` → Scripting → Text Editor 选择 `queen_mary.py` → Run Script。脚本会清空当前场景的所有对象并重新生成；造型修改应保存到外部 `queen_mary.py`。GUI 手调不会被下次生成保留。

脚本使用 Blender 3.x/4.x 共用 API，并处理预览色彩设置差异；实际执行版本为 **4.5.14 LTS**，没有分别在每个 3.x/4.x 版本运行。生成过程中出错会写入 `build_result.json` 的 traceback。先修正脚本，再重建；不要把旧 FBX 的存在视为本次构建成功。

## 尺度和坐标

| 项目 | 约定 |
|---|---|
| Blender 长度单位 | 1 单位 = 1 米，物体缩放为 1 |
| Blender 轴向 | +X 右舷，+Y 舰艏，+Z 向上 |
| 舰体根原点 | 船长中点、中线、水线交点 (0,0,0) |
| `Hull` 包围盒 | X 27.2 × Y 213.4 × Z 15.0 m |
| 舰体纵向 | Y = −106.7 … +106.7 m |
| 龙骨 / 水线 / 主甲板 | Z = −9.9 / 0 / +5.1 m |
| 艏楼甲板 | Z = +7.5 m，局部抬高 2.4 m |
| 27.2 m 舰宽口径 | 仅船体；副炮、网杆等附件可能超出船体宽度 |

排水量 27,200 / 32,158 t、航速 28 节和炮口径等保存在 `Queen_Mary` 自定义属性及 manifest 内。它们不是从网格体积推导的模拟结果；本模型不验证排水量、稳性、浮力或阻力。

## 估算布局

以下部件坐标是依据用户参考图做的灰盒估算，不是测绘值。`queen_mary.py` 顶部的 `STATIONS`、`TURRETS`、`FUNNELS`、`CASEMATE_YS` 是主要调整入口。修改主尺度时，应同时校核纵向站点、部件位置和验收尺寸。

| 对象 | 中心 Y（m） | 炮塔底 Z / 说明 |
|---|---:|---|
| Turret_A | +60 | +8.5，朝艏 |
| Turret_B | +46 | +12.0，朝艏，较 A 高 3.5 m |
| Bridge / Mast_Fore | +32 | 前桅在第一烟囱之前 |
| Funnel_1 | +23 | 椭圆截面：4.9 × 7.6 m |
| Funnel_2 | +7 | 圆形截面：直径 7.0 m |
| Turret_Q | −6 | +8.5，位于第二／第三烟囱之间，静置朝艉 |
| Funnel_3 | −27 | 椭圆截面：4.9 × 7.6 m |
| Mast_Main | −38 | 第三烟囱之后 |
| Turret_X | −68 | +6.3，朝艉 |
| Sternwalk | 约 −102 | 环绕舰艉的 U 形平台，保留简化栏杆 |

副炮每侧 8 门，从前往后编号，Y = 54、48、42、36、30、24、18、12 m。炮廓开口用深色凹口代理表达，没有做布尔镂空和炮廓内部。烟囱黑色顶部为简化盖面，没有内部烟道。防雷网以收起网束和贴舷撑杆表达，不生成密集网格。

## 层级和炮塔控制

```text
Queen_Mary
├─ Hull / Forecastle
├─ Superstructure
│  ├─ Bridge / Conning_Tower / Bridge_Upper
│  └─ Aft_Deckhouse / Rangefinder …
├─ Barbette_A                    固定炮座，B/Q/X 同理
├─ Turret_A                      炮塔盒本身也是水平旋转枢轴
│  └─ Elevation_A                炮塔前部的共同俯仰枢轴
│     ├─ Barrel_A_Port           单根炮管原点也在耳轴处
│     └─ Barrel_A_Starboard
├─ Turret_B / Turret_Q / Turret_X
├─ Funnel_1 / Funnel_2 / Funnel_3
├─ Mast_Fore / Mast_Main         每组含三根 Leg 和简化桅顶
├─ Casemate_Port_1 … 8
├─ Casemate_Starboard_1 … 8
├─ Sternwalk
├─ Torpedo_Net_Port_Stowed / Torpedo_Net_Starboard_Stowed
└─ Damage_Module_Anchors
   ├─ Magazine_A / B / Q / X
   ├─ Engine_Room_1 / Boiler_Room_1
   └─ Rudder / Fire_Control
```

Blender 中炮塔绕自身局部 Z 轴旋转；`Elevation_*` 绕局部 +X 轴正转可抬炮。A/B 初始水平旋转为 0°，Q/X 为 180°。俯仰原点在炮塔局部 `(0,4.0,1.5)` m，双炮管位于该枢轴两侧。

`Magazine_*`、动力舱、锅炉舱、舵和火控模块为定位空对象，均标记 `placeholder_only`，不具备舱室边界、命中检测、装甲或损伤逻辑。`Bridge` 是灰盒实体，`Rangefinder` 是简化横杆代理。没有实现炮塔射界限制、全角度防碰撞或弹道；验收仅检查静置炮管与主要上层建筑的相交情况。

## Unity 2022.3 导入约定

在独立临时工程中实际导入，未修改 `ThinkingFactory`。采用：

- Scale Factor = 1，Use File Scale = true。
- Bake Axis Conversion = true，Preserve Hierarchy = true。
- 不导入相机、灯光；资产类型使用普通模型，不启用 Humanoid。
- 测试关闭了材质导入，仅验证几何与层级。URP 中为材质槽指定简单的 `Universal Render Pipeline/Lit` 灰色材质；Blender 节点材质不能视为已验证的 URP Shader。

导入后船体世界尺寸应约为 **X 27.2 × Y 15.0 × Z 213.4 m**，船头朝 Unity +Z，龙骨 Y≈−9.9，主甲板 Y≈+5.1。FBX 会保留转换后的根变换和子对象局部坐标，**不要随意清零导入模型内部的旋转**。可在外层新增一个位置／旋转为零、缩放为一的游戏控制根对象。

在上述实际测试的导入设置下，炮塔局部轴与 Unity 世界轴不同。记录导入时的初始局部旋转，在其基础上叠加命令：

```csharp
// 在初始化时保存，不能在每帧更新中重新记录。
Quaternion restYaw = turret.localRotation;
Quaternion restPitch = elevation.localRotation;

// 更新时：yawDeg > 0 向本炮塔初始朝向的右侧转；elevationDeg > 0 抬炮。
turret.localRotation = restYaw * Quaternion.AngleAxis(-yawDeg, Vector3.forward);
elevation.localRotation = restPitch * Quaternion.AngleAxis(-elevationDeg, Vector3.right);
```

Q/X 的 `yawDeg` 是相对各自朝艉的初始方向；若控制器使用全舰统一方位角，应先减去该炮塔初始方位。重新更改导入设置或烘焙方式后，应重新验证轴向和符号。

## 验收文件和历史边界

- `verification.json`：保存后的 Blender 场景尺寸、布局、16 门副炮、三脚桅、阳台、模块、枢轴运动和静置相交检查。
- `fbx_verification.json`：空场景真实重导入 FBX 后，检查对象、父子关系、世界包围盒、尺寸和四座炮塔运动。
- `unity_verification.json`：Unity 2022.3.62f3c1 真实导入记录，包含被验收 FBX 的 SHA-256、尺寸和方向检查。
- `build_result.json`：实际 Blender 版本、时间戳和同进程二次生成结果。`object_manifest.json` 中的几何签名包含名称、变换、顶点和面，可跨重建比较；FBX 二进制文件哈希可能因导出时间变化。

参考素材：第一张线图用于主要布置；第三张彩图明确标注 05/1916，只借用共同轮廓与布局；第二张照片没有经过舰名及日期核实，只作一般炮塔／舰桥层次参考。本轮按用户明确要求保留“两座三脚桅”和“左右各 8 门艏楼副炮”，不将它们描述为已考证的 1913 年全套配置。

补充核对过的馆藏资料：[Royal Museums Greenwich — Queen Mary 馆藏模型](https://www.rmg.co.uk/collections/objects/rmgc-object-67366)。馆方给出约 700 英尺舰长、89 英尺舰宽，与本轮用户指定的 213.4 / 27.2 m 主尺度接近；该网页不用于认证本轮各部件估算尺寸和两座三脚桅方案。

下一阶段可在稳定语义 ID 上增加舰体碰撞代理、舱室体积、炮塔射界与 Unity Prefab，然后再验证损伤及 AI Agent 控制。当前资产尚未包含 LOD 组、舰队逻辑或战斗系统。
