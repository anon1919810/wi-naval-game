# HMS Queen Mary · 一战英国战列巡洋舰游戏资产

一艘 **1913 年 9 月服役原状**的战列巡洋舰「玛丽王后号」，用一份 Python 脚本在 Blender 里程序化生成，
带多层自动验证，并已接入 Unity（URP）。

- **性质**：灰盒（greybox），**不是**经过考证的精确复原——`historically_certified: false` 写在数据里
- **用途场景**：中距 50–200 m 观察，同屏 10–30 艘
- **当前资产版本**：**v3**（`queen_mary_v3/`），101 对象 / 85 网格 / 31,164 三角面

> 本仓库于 2026-09-18 建立。**此前的历史无法重建**，仓库从那一刻开始记录；
> v2 的目录按原样保留，作为只读历史。

## 目录地图（融合后只有一个家）

| 路径 | 是什么 |
|---|---|
| **`queen_mary_v3/`** | **当前资产**：`.blend` / `.fbx` / 七份 JSON / 预览图 / `rebuild.ps1` / `verify_*.py` |
| **`queen_mary_v3/unity/`** | **唯一的 Unity 集成家**：Editor 工具、契约类、同步脚本、`README_集成.md` |
| `queen_mary_v3/docs/legacy_codex_unity/` | 归档：另一条产线写的并行实现（**不要拷进工程**） |
| `queen_mary/` | 只读历史：v2 资产（98 对象）与其 45 项验证链 |
| `参考素材/` | 三张参考图，**都不可作为确定证据** |
| `交接文件_GPT6_2026-09-17.md` | 历史交接文档（v2 视角，开头有 v3 指针） |

## 一条命令跑完

```powershell
cd "C:\Users\杨睿\Desktop\HMS_Queen_Mary_建模成果_2026-09-17\queen_mary_v3"
.\rebuild.ps1            # 重建资产 + 45 项 Blender 侧检查（32 几何 + 13 史实）
```

要不要同步到 Unity 工程（`D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval`）：

```powershell
cd "...\queen_mary_v3\unity"
.\sync_to_unity.ps1 -ProjectPath "D:\Unity\Projects\QueenMaryNaval\QueenMaryNaval"
```

Unity 侧三道门（都能用 `-batchmode -executeMethod` 跑，不用开界面）：

| 菜单 | 批处理入口 | 验什么 |
|---|---|---|
| Set up URP | `Naval.EditorTools.UrpSetup.SetUpBatch` | 建 URP 管线资产、按契约建材质、重导模型 |
| Validate ship asset | `Naval.EditorTools.ShipAssetValidator.ValidateBatch` | 契约 101 名、轴向、URP 材质、炮塔枢轴 |
| Render URP check images | `Naval.EditorTools.ShipPreviewRender.RenderBatch` | 逐像素查品红/黑屏，出五张校验图 |

当前状态：**三道门全绿**（`unity_verification_urp.json`、`unity_render_check.json`）。

## 改动约定（谁改了什么）

1. **改资产 → 必须重建并跑验证**，把 `geometry_sha256` 的变化写进提交信息或交接记录，
   不要以"我记得改过"结案。
2. **不要手填绝对坐标**，贴体附件一律从 `halfbeam_at(y, z)` 派生。
3. **契约是唯一字段来源**：Unity 侧不要从 `object_manifest.json` 手抄字段；
   FBX 文件名也从契约读（`file_refs.fbx`），别硬编码。
4. **断言要写物理不变量，不要写实现细节**——曾经把"炮管局部位置必须为 0"写成断言，
   换代时立刻误报（正确写法是"原点落在耳轴上"）。
5. 不要把灰盒设定写成史实断言：新加的历史结论要么有 `source`，要么标 `user_spec_only`。
6. **C# 静态预检要对 Unity 工程跑，不要对 `queen_mary_v3/unity/` 跑**：

   ```bash
   cd D:/Unity/Projects/ThinkingFactory
   python tools/cs_precheck.py "D:/Unity/Projects/QueenMaryNaval/QueenMaryNaval"
   ```

   它按 `<根>/Assets/**/*.cs` 找文件；融合后的 `unity/` 是 `Editor/` + `Scripts/` 结构，
   直接指过去会**扫到 0 个文件然后报"全部通过"**——那是假绿，不是真的过了。
   （同理，预检通过 ≠ 能编译，改完必须真的让 Unity 编一次。）
