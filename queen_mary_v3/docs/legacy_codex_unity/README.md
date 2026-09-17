# 归档：Codex 产线那一版 Unity 导入检查器

这里放的是 v3 产线（Codex）自己写的那套 Unity 导入检查器原文件，**仅作留档，不要再拷进工程**。

- `Editor/QueenMaryImportCheck.cs`
- `Scripts/ShipContract.cs`

## 为什么归档

它和本仓库的 `unity/Editor/ShipAssetValidator.cs` + `unity/Scripts/ShipContract.cs` 做的是同一件事，
两份并存会导致：同一个契约字段改一处漏一处，而"什么算验证通过"出现两个标准。

融合后的唯一家是 **`queen_mary_v3/unity/`**：

| 保留 | 说明 |
|---|---|
| `unity/Scripts/ShipContract.cs` | 契约加载（含 `FbxFileName()` 从契约读文件名） |
| `unity/Editor/ShipAssetValidator.cs` | 契约 / 层级 / 轴向 / 材质 / 炮塔枢轴校验 |

## 从这份归档里并进来的东西

它有两处比我们原来的强，已经并进 `ShipAssetValidator`，**记在这里以免有人再写第二遍**：

1. **物理右舷方向**：`(Casemate_Starboard_1 - Casemate_Port_1).normalized` 必须朝 Unity +X。
   这是唯一能判出左右手性的做法 —— 船体左右对称，任何对船体本身的检查都判不出左右，
   但左右舷的副炮**自带名字**，两个有标注的点一减就是答案。
2. **逐炮塔的轴表**（A/B/Q/X 各自的偏航轴、俯仰轴与符号）：只看汇总的一致性会盖住
   "某一座塔单独跑偏" 的情况。

它那份 `ShipContract.cs` 与我们的字段基本一致（都是 `JsonUtility` 扁平结构），没有独有的字段，
所以只保留我们这一份。
