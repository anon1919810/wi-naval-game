# 验证报告发布恢复（Task 1 / F08）

本文件记录 `tools/plimsoll/verification_report.py` 的发布重试契约、`tools/plimsoll/app.py` 的期限传递方式，以及本机可复现的证据边界。**未**声明任何具体外部成因：**宿主上的所有者/策略来源未经识别**，因此这里只实现有界处理，不把未查明的成因写成结论。

## 起因（既有证据，非本次新测）

- 真实 `verify --suite quick` 两次在 `os.replace(tmp, core-verification.csv)` 处失败，`WinError 5`，命令退出 1，**没有留下任何证据**。
- 隔离的 stdlib 循环 100 次中出现 2 次同类失败。
- 现象与本文件所列 WinError 5 一致，但**持有者/策略来源未确认**；因此恢复逻辑不假定成因，只对已识别的瞬时码做有界重试，其余一律立即失败。

本次改动没有改动物理、数值容差、schema 字段或输出格式，只改“证据如何落盘”。

## 只重试已识别的瞬时拒绝

| 条件 | 行为 |
|---|---|
| `os.replace` 抛错且 `winerror ∈ {5, 32, 33}`（5 ACCESS_DENIED、32 SHARING_VIOLATION、33 LOCK_VIOLATION） | 有界重试 |
| 无 `winerror`（全部 POSIX 平台，或 `OSError(errno, …)` 未带 Windows 码） | 立即抛出，不重试 |
| 其他 Windows 码（如 1117） | 立即抛出，不重试 |
| 替换**之前**的失败（临时文件创建、写、flush、fsync） | 立即抛出，不重试 |
| 每次尝试前的复检失败（目标变化、锁被夺走、临时源消失/被替换、reparse、外来文件） | 立即抛出，不重试 |

分类只看 `winerror`，不看 `errno`：同一 `errno` 在不同平台含义不同，且 POSIX 上根本不存在该字段。常量：`TRANSIENT_REPLACE_WINERRORS`、`REPLACE_RETRY_BACKOFF_S = (0.01, 0.02, 0.04, 0.08, 0.16)`、`REPLACE_RETRY_ATTEMPTS = 6`、`PUBLISH_RETRY_BUDGET_S = 0.5`。

## 每次尝试都重新证明所有权

写入与 fsync 只做一次，随后**同一个自有临时文件**被重复尝试使用；**每一次** `os.replace` 之前（第一次、每次退避睡眠之后）都重新执行：

1. `preflight_destinations(directory)`：三个固定名全部重查（归属、schema、reparse、可读性）；
2. `_require_lock(directory, token)`：**精确 token** 比对，锁被换掉即失败；
3. 目标签名（dev/ino/size/mtime + SHA-256）必须仍等于本次写入前捕获的 `expected`；
4. 临时源必须同时匹配**本次创建的那个文件**与**本次渲染出的字节**：用创建时从描述符取得的 (dev, ino) 判定（`_is_our_file`），并把签名的 SHA-256 与真正写入的字节比对，在**签名之后立刻**证明一次（签名期间被换 inode 或被改写内容的文件都不会被采纳为源），此后每次尝试再证明身份与内容签名；
5. **每一次重试**在 `os.replace` 之前再次读取单调时钟（第一次尝试不受此限，见下）。

因此“替换失败 → 睡眠 → 目标已被别人改写”不会覆盖新内容：宁可拒绝发布并保留磁盘原样。**绝不**先 unlink 目标、**绝不**改用非原子覆盖。清理只删除**本次创建**的那一个文件，且删除前先用创建时从描述符取得的 (dev, ino) 证明归属；一旦检测到替换或内容变化，该路径被**保留**供人工恢复而不是删除。派生 CSV、Markdown 仍然先于权威 JSON，JSON 最后——重试不改变顺序，也不改变“混合代次必须被读者拒绝”的规则。

## 期限语义（精确）

`write_report(report, output_dir, *, retry_deadline=None)`：新增参数**仅关键字**，旧的两位置调用完全不变，不写入报告 schema，也不使用任何可变全局期限。

- `retry_deadline` 是**绝对 `time.monotonic()` 时刻**；必须是有限非布尔的数字，否则在任何写动作之前抛 `ReportError`。
- 每次替换的等待上限 = `min(本次替换开始时刻 + PUBLISH_RETRY_BUDGET_S, retry_deadline)`。预算从**这一次替换**开始计时而非整轮运行；因为三个目标各自都可能瞬时失败后再成功，一次快照最多可花掉**三个**替换级预算，并且还会被同一个调用方期限进一步裁剪；而任何**永久**失败会中止尚未尝试的目标。
- 语义只约束**等待**：退避不会睡过该时刻；睡眠是尽力而为，调度器可能比请求更晚返回，所以保证不是硬实时的唤醒时刻，而是**每次重试在 `os.replace` 之前重新读取时钟**——一旦观察到期限已过就不再发起新的替换，并以**原始拒绝错误**（WinError 与诊断 note 一并保留）结束，而不是照样替换或伪装成功。第一次尝试永不被扣留，否则总期限之后的最终失败证据将无法落盘。
- 期限**只限制等待，绝不扣留本可发布的报告**：即使期限已过，快照仍会以单次尝试落盘。
- 传 `None` 表示“使用模块自身的有限预算”；传一个已过去的时刻表示“禁止重试”，二者都不改变发布语义。
- `app.py` 的 `verify` 传入 `time.monotonic() + args.total_timeout_s`（一个局部值）：运行器从其 `started` 起算总预算，因此该时刻**略早于**运行器口径，属于保守裁剪。期限耗尽后，最终失败证据的发布退化为原有的**单次、不重试**尝试。
- 未改变运行器既有行为：checkpoint 的耗时仍计入总期限，父进程仍在总期限后不接受通过的快照；重试等待计入该预算，这只会让“发布期超时”更可能诚实发生，而不是被掩盖。

## 失败时保留什么

尝试上限（6 次）或等待预算（0.5 s/目标，或调用方期限）先到即停止：原始 `OSError` 连同诊断 note 向上抛出，`write_report` 包装为 `PublishError`，其**消息字符串**记录 `replaced=[…] pending=[…]`，而 note 只存在于 `PublishError.__cause__.__notes__`（traceback 与 note 打印中可见），不会出现在该字符串里。

- 已替换的文件保持新字节，未替换的保持旧字节：**因此混合代次仍然可能出现，并且必须被读者拒绝**（`read_published` 的 `identity_match=False`、`passing=False`）。
- 本次发布**不保证**留下任何一份旧的完整快照：若被拒的正是 JSON 目标，磁盘上留下的正是“派生文件新、权威 JSON 旧”的混合状态。若目录此前没有报告，失败后可以为空。
- 失败绝不会变成通过：未发布新权威 JSON 时，读者读到的仍是上一代字节或无文件。

## 证据

新增 `tools/plimsoll/tests/test_verification_publication_retry.py`（55 项）。除注入的 `os.replace` 拒绝（以及期限判据用的注入时钟）外全部为真实行为：真实临时文件、真实 fsync、真实签名、真实原子替换、真实 `read_published` 读者探测。

独立复核（Codex，review round 1）在该目录下的 `test_publication_review_edges.py` 中给出探针：初次运行 **2 failed**（调度器超时醒来后仍发起第二次替换；清理删除了被替换的外来 inode）；随后又追加两条源归属探针（签名期间被换 inode、以及同 inode 被改写内容时的采纳），修复后全部 **4 passed**（`review1-green-probes.txt`）。四条均已提升为产品测试。

- 先红后绿：红 **28 failed / 13 passed**（`retry_deadline` 不存在、瞬时拒绝直接失败）；实现后全部通过。
- 真实恢复：三个目标 × 三个 WinError 码 × 两次拒绝 → 发布成功，读者 `passing=True`、`identity_match=True`，同一个临时文件被复用，无临时/锁残留。
- 有界：永久拒绝时尝试次数不超过 6、等待 ≥0.30 s 且 < 5 s；权威 JSON 保留旧字节，派生文件已是新字节，混合代次被拒绝（**不声称**磁盘上一定留有一份旧的完整快照）。
- 不重试：`errno=5` 但无 `winerror`、POSIX `EACCES`、`ENOSPC`、WinError 1117 各只尝试一次且一次睡眠都没有；替换前的 `fsync` 拒绝时 `os.replace` 一次都不被调用。
- 不覆盖：目标被改写（仍合法的他人 CSV）、外来目标出现、锁被换 token、临时源消失、临时源被占用文件替换——均拒绝发布并保留磁盘内容。
- 清理归属：临时路径被换 inode（永久失败、无后续复检）与被写入外来内容（同一 inode）两种情况都**保留**该文件并在 note 中说明；真正属于自己的临时文件在替换失败后仍然被删除、无残留。
- 源归属：在**签名过程中**被换 inode 或被改写内容（同 inode）的文件都不会被采纳为自己的源（`os.replace` 一次都不被调用，外来字节不落到任何目标）。
- 期限（注入时钟的精确判据）：`retry_deadline=1000.30` 时睡眠恰为 `[0.01,0.02,0.04,0.08,0.15]`（合计 0.30 s）并恰好 5 次尝试；`retry_deadline=1000.05` 且每次睡眠超时 1.0 s 时只有 1 次 `os.replace`、抛出的仍是原始 WinError 5；已过期期限 0 次睡眠 1 次尝试；无调用方期限时 6 次尝试的封顶仍成立；晚醒的超大 oversleep 由 0.5 s 预算截断为 1 次尝试。
- CLI：总期限充足时有界且不放大预算；总期限已耗尽时第一次替换只尝试一次；一次瞬时拒绝后 CLI 仍发布出**同一代次**的三份文件；`.01 s` 总期限的最终超时证据仍是三份一致、非通过的失败证据。
- 公开契约未变：一次真实 CLI 运行后，发布 JSON 的顶层字段集合与 CLI 摘要 `plimsoll-cli-verification-summary-1` 的字段集合逐项比对，与改动前一致，且正文不含 `retry_deadline`/预算常量。
- 相邻回归（未改动但受影响的路径）：`test_cli_readme`、`test_core_cli`、`test_audit_cli_runtime`、`test_exports`、`test_package_imports`、`test_verification_cases` **113 passed + 37 subtests**（194.15s）。

验收命令（`PYTHONPATH` 指向绝对 `repo/tools`）：

```powershell
$env:PYTHONPATH = (Resolve-Path -LiteralPath './tools').Path
& web/backend/.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider `
  tools/plimsoll/tests/test_verification_report.py `
  tools/plimsoll/tests/test_cli_verify.py `
  tools/plimsoll/tests/test_verification_runtime.py `
  tools/plimsoll/tests/test_verification_publication_retry.py
```

结果：基线 **178 passed, 2 skipped**（41.43s）→ 含新增用例 **224 passed, 2 skipped**（118.48s）。

## 已知限制与适用范围

- 重试**不是**三文件事务：替换失败后仍是“已替换的保留新字节、未替换的保留旧字节，读者拒绝混合代次”。本次未改变这一点；混合代次在磁盘上是真实可能的状态，不是异常。
- 最后一次复检与 `os.replace` 系统调用之间的微小竞态依旧存在（不可消除）；本文件只保证**不会跨过睡眠盲写**。
- 睡眠是尽力而为：调度器晚醒时，被裁剪的那一次退避仍会睡满剩余时间，随后由替换前的时钟复核拒绝重试——因此可能出现“等到了期限却不再尝试”，这是刻意的（宁可保留旧字节，也不越过调用方期限）。
- 本机实测：一次 `write_report` 约 0.09–0.25 s，首次拒绝出现在调用后约 0.08–0.13 s。在这样的文件系统上，0.5 s 的替换级预算通常只够 **5 次**尝试（复检成本吃掉了 6 次所需的余量）；文件系统更快时才走满 6 次封顶。更慢的文件系统只会**少**几次尝试，不会等待更久。
- 永久拒绝（例如宿主策略持续拒绝替换）不会被“重试成功”：命令仍退出 1 且不发布新的权威 JSON；已存在的文件保持各自当时的字节（可能是混合代次，必须被读者拒绝），此前没有报告时目录可以为空。
- 测试中的瞬时拒绝是注入的，不是本机自然复现；本文件不声称已复现或已修复那个未查明的宿主成因。
- 本文件只覆盖 Task 1（F08）。后续 Task 2 以及 Codex 对真实主机发布和物理方法的独立验收见[2026-10-15 验收记录](reliability-stability-2026-10-15.md)，本文件中的初始测试数字不代替最终验收。
