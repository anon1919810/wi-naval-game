# Task 1 scoped re-review — e5f2ee0..b9c0a22

Reviewer /root/plimsoll_contract_review: APPROVED. All three Important findings ADDRESSED; no new breakage or out-of-scope observations.

- project_io.py:240 skips already-diagnosed non-string hull keys; regression covers validation and normalization without AttributeError.
- project_io.py:117 preserves missing item estimate as null; :581 diagnoses estimate.unknown. Declared flags remain intact, and fingerprint distinguishes unknown from explicit false.
- project_io.py:312 restricts geometry to supported kinds and matching payload shapes. Reference requires path, parameters require nonempty object, offsets require object/nonempty stations. Structural validation does not scan filesystem or duplicate hull physics.
- Reported RED exercises original defects; 21/21 focused GREEN covers fixes. No redundant suite or probe run.

Task 1 complete: implementations 5e06a01 and b9c0a22; initial 343-test full regression plus 21-test post-fix focused run. This is the Task 1 gate, not full stage A or product completion.
