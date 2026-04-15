# Write Tag — Exhaustive UI Mapping

## Covered Activities

| Activity              | Binary symbol prefix                            | .so file          |
|-----------------------|-------------------------------------------------|-------------------|
| WarningWriteActivity  | `__pyx_pw_13activity_main_20WarningWriteActivity_` | activity_main.so |
| WriteActivity         | `__pyx_pw_13activity_main_13WriteActivity_`       | activity_main.so  |

Binary source: `/home/qx/icopy-x-reimpl/decompiled/activity_main_ghidra_raw.txt`
String table: `/home/qx/icopy-x-reimpl/src/lib/resources.py` (StringEN dicts)

---

## 1. WarningWriteActivity — Pre-Write Confirmation

### 1.1 Activity Identity

- **ACT_NAME**: `warning_write`
- **Binary methods** (from STR table, activity_main_ghidra_raw.txt):
  - `__init__` (line 353, @0x00034074)
  - `onCreate` (line 532, @0x000cc4f8)
  - `finish` (line 484, @0x00060ce0)
  - `onData` (line 338, @0x00031af0)
  - `onKeyEvent` (line 558, @0x000ccbb0)

### 1.2 Purpose

WarningWriteActivity is the pre-write confirmation screen. It is displayed after a successful read (from ReadActivity or AutoCopyActivity) to confirm that the user wants to write data to a new tag.

Reached from:
- ReadActivity: M2/OK after "Read Successful!" toast
- AutoCopyActivity: internal flow after scan+read success (displayed as "Data ready!" screen)
- CardWalletActivity (Dump Files): selecting a dump file for writing

### 1.3 Screen Layout

**Title**: "Data ready!" — `resources.get_str('data_ready')` = `"Data ready!"` (resources.py line 84)

```
+---------------------------------------+
|  Data ready!               [battery]  |  <- Title: "Data ready!" (Consolas 18, white)
+---------------------------------------+
|                                       |
|  Data ready for copy!                 |  <- tipsmsg 'place_empty_tag' text
|  Please place new tag for copy.       |
|                                       |
|  TYPE:                                |  <- tipsmsg 'type_tips' prefix
|  M1-4b                                |  <- Tag type short name
|                                       |
+---------------------------------------+
|  Watch                   Write        |  <- M1="Watch" or "Cancel", M2="Write"
+---------------------------------------+
```

**Evidence**: `Step - 3.png` shows this exact layout: title "Data ready!", content "Data ready for copy! Please place new tag for copy.", "TYPE: M1-4b", buttons "Watch" and "Write".

**Note**: In the AutoCopy flow, the M1 button says "Watch" (for wearable write). In the standalone ReadActivity flow, the M1 button says "Cancel". The M2 button is always "Write".

### 1.4 Content Text

Source: resources.py StringEN.tipsmsg (lines 152-153):
- `place_empty_tag` = `"Data ready for copy!\nPlease place new tag for copy."` (line 152)
- `type_tips` = `"TYPE:"` (line 153)

The display combines:
1. The `place_empty_tag` message (multi-line prompt)
2. The `type_tips` prefix + tag type short name

### 1.5 Key Bindings — WarningWriteActivity

Source: decompiled `onKeyEvent` at line 558 (@0x000ccbb0).

| Key   | Action                                        |
|-------|-----------------------------------------------|
| M1    | finish() — cancel write, return to caller     |
| M2    | Confirm write: finish with result `{action: 'write'}`, proceeds to WriteActivity |
| OK    | Same as M2                                    |
| PWR   | finish() — cancel/back (universal exit)       |

### 1.6 Button Labels

| Button | Label                | resources key   |
|--------|----------------------|-----------------|
| M1     | "Cancel"             | `'cancel'`      |
| M2     | "Write"              | `'write'`       |

In AutoCopy context, M1 may show "Watch" (for wearable write flow).

**Evidence**: `Step - 3.png` shows "Watch" (M1) and "Write" (M2).

### 1.7 __init__

Source: decompiled at line 8276 (@0x00034074).

Parameters: `(self, infos)`

The `__init__` method:
1. Calls super().__init__(self, infos)
2. Sets `self.infos` = the infos parameter (read data bundle)

The decompilation (line 8437) shows `CallOneArg(piVar1, iVar14)` where `iVar14` is the second positional argument (infos). After the super init call, `SetAttr(piVar11, ..., piVar8)` stores a reference to None on the instance.

### 1.8 finish — Result Passing

Source: decompiled at line 48125 (@0x00060ce0).

When M2/OK is pressed (confirmation), the `finish` method packages the tag info bundle as a result for the parent activity. The parent (ReadActivity or AutoCopyActivity) then launches WriteActivity with this data.

### 1.9 onData

Source: decompiled at line 6207 (@0x00031af0).

The `onData` method receives callbacks from the write module with status updates. In WarningWriteActivity, this is primarily used for pre-write validation (e.g., checking if the destination tag is compatible).

---

## 2. WriteActivity — Write + Verify

### 2.1 Activity Identity

- **ACT_NAME**: `write`
- **Binary methods** (from STR table, activity_main_ghidra_raw.txt):
  - `__init__` (line 583, @0x000cd198)
  - `onCreate` (line 611, @0x000cd80c)
  - `onKeyEvent` (line 537, @0x000cc624)
  - `onData` (line 390, @0x000ca48c)
  - `startWrite` (line 547, @0x000cc918)
  - `startVerify` (line 549, @0x000cc988)
  - `on_write` (line 628, @0x000cdbfc)
  - `on_verify` (line 617, @0x000cd964)
  - `setBtnEnable` (line 637, @0x000cde04)
  - `playWriting` (line 643, @0x000cdf6c)
  - `playVerifying` (line 644, @0x000cdfa4)

### 2.2 State Machine

```
                     +-- M1/OK --> startWrite() --> WRITING --> on_write()
                     |                                             |
     IDLE -----------+                                    +--------+--------+
(initial state)      |                                    |                 |
                     +-- M2 ----> startVerify() -> VERIFYING  WRITE_SUCCESS  WRITE_FAILED
                                                      |          |              |
                                               on_verify()    M1=Verify      M1=Verify
                                                   |           M2=Rewrite    M2=Rewrite
                                            +------+------+
                                            |             |
                                     VERIFY_SUCCESS  VERIFY_FAILED
                                       M1=Verify      M1=Verify
                                       M2=Rewrite     M2=Rewrite
```

### 2.3 State: IDLE — Initial Write/Verify Prompt

**Title**: "Write Tag" — `resources.get_str('write_tag')` = `"Write Tag"` (resources.py line 85)

```
+---------------------------------------+
|  Write Tag                 [battery]  |  <- Title: "Write Tag"
+---------------------------------------+
|  MIFARE                               |  <- Tag family (from infos)
|  M1 S50 1K (4B)                       |  <- Tag type
|  Frequency: 13.56MHZ                  |  <- Frequency
|  UID: 2CADC272                        |  <- UID
|  SAK: 08  ATQA: 0004                  |  <- SAK/ATQA
|                                       |
|                                       |
+---------------------------------------+
|  Write                  Verify        |  <- M1="Write", M2="Verify"
+---------------------------------------+
```

**Button labels**:
- M1: "Write" — `resources.get_str('write')` = `"Write"` (resources.py line 42)
- M2: "Verify" — `resources.get_str('verify')` = `"Verify"` (resources.py line 51)

### 2.4 State: WRITING — Write in Progress

**Evidence**: `Step - 4.png`

```
+---------------------------------------+
|  Write Tag                 [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)                       |
|  Frequency: 13.56MHZ                  |
|  UID: 2CADC272                        |
|  SAK: 08  ATQA: 0004                  |
|                                       |
|            Writing...                 |  <- procbarmsg 'writing' = "Writing..."
|  [====       progress bar       ]     |  <- ProgressBar widget, blue fill
+---------------------------------------+
|  (buttons disabled/greyed)            |  <- setBtnEnable(False)
+---------------------------------------+
```

**Evidence**: `Step - 4.png` shows "Write Tag" title, tag info (MIFARE M1 S50 1K 4B, UID 2CADC272), "Writing..." message, and active progress bar. No button labels visible (buttons disabled).

### 2.5 State: WRITE_SUCCESS

Toast: `toastmsg['write_success']` = `"Write successful!"` (resources.py line 115)

```
+---------------------------------------+
|  Write Tag                 [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)     +-------------+  |
|  Frequency: 13.56MHZ| Write       |  |
|  UID: 2CADC272       | successful! |  |  <- Toast overlay with checkmark
|  SAK: 08  ATQA: 0004+-------------+  |
|                                       |
+---------------------------------------+
|  Verify               Rewrite        |  <- M1="Verify", M2="Rewrite"
+---------------------------------------+
```

Button labels after success:
- M1 (left): "Verify" — `resources.get_str('verify')` = `"Verify"` (resources.py line 51)
- M2 (right): "Rewrite" — `resources.get_str('rewrite')` = `"Rewrite"` (resources.py line 49)

**Evidence**: `autocopy_mf1k_gen1a/0800.png` shows "Verify" on left and "Rewrite" on right after "Write successful!" toast. Same button order as write failure.

### 2.6 State: WRITE_FAILED

**Evidence**: `Step - 5.png`

Toast: `toastmsg['write_failed']` = `"Write failed!"` (resources.py line 117)

```
+---------------------------------------+
|  Write Tag                 [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)     +-------------+  |
|  Frequency: 13.56MHZ| X Write     |  |
|  UID: 2CADC272       |   failed!   |  |  <- Toast overlay with X icon
|  SAK: 08  ATQA: 0004+-------------+  |
|                                       |
+---------------------------------------+
|  Verify               Rewrite        |  <- M1="Verify", M2="Rewrite"
+---------------------------------------+
```

**Evidence**: `Step - 5.png` shows "Write Tag" title, tag info, "Write failed!" toast with X icon, and button bar showing "Verify" (left) and "Rewrite" (right).

After write failure, the button labels are:
- M1 (left): "Verify" (resources.py line 51)
- M2 (right): "Rewrite" (resources.py line 49)

This is the SAME order as write success. Both success and failure show M1="Verify", M2="Rewrite".

**Screenshot citation**: `write_tag_write_failed.png` shows "Write failed!" toast with X icon, M1="Verify" on left, M2="Rewrite" on right — identical button order to `autocopy_mf1k_gen1a/0800.png` (success).

### 2.7 State: VERIFYING — Verification in Progress

```
+---------------------------------------+
|  Write Tag                 [battery]  |
+---------------------------------------+
|  MIFARE                               |
|  M1 S50 1K (4B)                       |
|  Frequency: 13.56MHZ                  |
|  UID: 2CADC272                        |
|  SAK: 08  ATQA: 0004                  |
|                                       |
|            Verifying...               |  <- procbarmsg 'verifying' = "Verifying..."
|  [====       progress bar       ]     |
+---------------------------------------+
|  (buttons disabled/greyed)            |
+---------------------------------------+
```

Progress message: `procbarmsg['verifying']` = `"Verifying..."` (resources.py line 182)

### 2.8 State: VERIFY_SUCCESS

Toast: `toastmsg['verify_success']` = `"Verification successful!"` (resources.py line 118)

Button labels (same order as all post-operation states):
- M1 (left): "Verify" — allows re-verification
- M2 (right): "Rewrite" — allows re-writing

### 2.9 State: VERIFY_FAILED

Toast: `toastmsg['verify_failed']` = `"Verification failed!"` (resources.py line 119)

Button labels:
- M1 (left): "Verify"
- M2 (right): "Rewrite"

### 2.10 Combined Write+Verify Success

When write is followed immediately by verify and both succeed:

Toast: `toastmsg['write_verify_success']` = `"Write and Verify successful!"` (resources.py line 116)

This toast is shown by AutoCopyActivity when both operations complete in sequence.

---

## 3. Key Bindings — WriteActivity (Complete)

### State matrix:

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | startWrite() | startWrite() | startVerify() | finish() |
| WRITING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| VERIFYING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | finish() |
| WRITE_SUCCESS | no-op | no-op | no-op | no-op | startWrite() | startWrite() | startVerify() | finish() |
| WRITE_FAILED | no-op | no-op | no-op | no-op | startWrite() | startWrite() | startVerify() | finish() |
| VERIFY_SUCCESS | no-op | no-op | no-op | no-op | startWrite() | startWrite() | startVerify() | finish() |
| VERIFY_FAILED | no-op | no-op | no-op | no-op | startWrite() | startWrite() | startVerify() | finish() |

### 3.1 State: IDLE

| Key   | Action                                        |
|-------|-----------------------------------------------|
| M1    | startWrite() — begin write operation (M1="Write" label) |
| M2    | startVerify() — begin verify operation (M2="Verify" label) |
| OK    | startWrite() — same as M1                     |
| PWR   | finish() — exit back to WarningWriteActivity  |

### 3.2 State: WRITING / VERIFYING

| Key   | Action                                        |
|-------|-----------------------------------------------|
| M1    | (disabled — setBtnEnable(False))              |
| M2    | (disabled — setBtnEnable(False))              |
| OK    | (disabled)                                    |
| PWR   | finish() — abort and exit                     |

### 3.3 State: WRITE_SUCCESS / WRITE_FAILED / VERIFY_SUCCESS / VERIFY_FAILED

| Key   | Action                                        |
|-------|-----------------------------------------------|
| M1    | startWrite() — rewrite (M1="Rewrite" label, LEFT) |
| M2    | startVerify() — verify (M2="Verify" label, RIGHT) |
| OK    | startWrite() — same as M1                     |
| PWR   | finish() — exit                               |

**CORRECTION (2026-03-31):** Previous version had M1 and M2 actions SWAPPED in success/fail states. Binary re-analysis confirms: M1/OK always maps to startWrite(), M2 always maps to startVerify(). Button labels after write: M1="Rewrite" (left), M2="Verify" (right). This is consistent across all result states.

**Evidence**: Button labels set by `_onWriteComplete` and `_onVerifyComplete`: `setLeftButton('Rewrite')`, `setRightButton('Verify')` (src/lib/activity_main.py lines 3307-3308).

---

## 4. Binary Method Details

### 4.1 startWrite

Source: STR table line 547 (@0x000cc918).

Flow:
1. `setBtnEnable(False)` — disable all button inputs
2. `playWriting()` — show "Writing..." progress bar
3. Start write.so write operation on background thread
4. On completion: call `on_write()` callback

### 4.2 startVerify

Source: STR table line 549 (@0x000cc988).

Flow:
1. `setBtnEnable(False)` — disable all button inputs
2. `playVerifying()` — show "Verifying..." progress bar
3. Start write.so verify operation on background thread
4. On completion: call `on_verify()` callback

### 4.3 on_write — Write Completion Callback

Source: STR table line 628 (@0x000cdbfc).

Receives write result from write.so:
1. Hide progress bar
2. If success: show "Write successful!" toast
3. If failure: show "Write failed!" toast
4. Set M1 (left)="Verify", M2 (right)="Rewrite" (same for both outcomes)
5. `setBtnEnable(True)` — re-enable buttons

**Evidence**: Both `autocopy_mf1k_gen1a/0800.png` (success) and `Step - 5.png` (failure) show identical button order: "Verify" left, "Rewrite" right.

### 4.4 on_verify — Verify Completion Callback

Source: STR table line 617 (@0x000cd964).

Receives verify result from write.so:
1. Hide progress bar
2. If success: show "Verification successful!" toast
3. If failure: show "Verification failed!" toast
4. Set M1 (left)="Verify", M2 (right)="Rewrite"
5. `setBtnEnable(True)` — re-enable buttons

### 4.5 setBtnEnable

Source: STR table line 637 (@0x000cde04).

When `enabled=False`:
- Both M1 and M2 button labels are greyed out (dimmed color)
- Key presses on M1/M2/OK are ignored in onKeyEvent

When `enabled=True`:
- Both M1 and M2 button labels restored to white
- Key presses are processed normally

### 4.6 playWriting

Source: STR table line 643 (@0x000cdf6c).

1. Cancel any active toast
2. Set ProgressBar message to "Writing..." (`procbarmsg['writing']`)
3. Set progress to 0%
4. Show progress bar

### 4.7 playVerifying

Source: STR table line 644 (@0x000cdfa4).

1. Cancel any active toast
2. Set ProgressBar message to "Verifying..." (`procbarmsg['verifying']`)
3. Set progress to 0%
4. Show progress bar

### 4.8 onData

Source: decompiled at line 14821 (@0x0003b5a8).

The `onData` method takes 2 parameters: `(self, key, value)`.

From the decompilation (lines 14913-14915):
1. `SetAttr(iVar10, ..., iVar9)` — stores the value on self
2. Calls a method on self (likely `updateDisplay()` or `processData()`)

This is the generic data callback from write.so that updates write progress percentage and status.

### 4.9 onCreate

Source: STR table line 611 (@0x000cd80c).

Flow:
1. `setTitle("Write Tag")`
2. Create ProgressBar widget
3. Create Toast widget
4. `setLeftButton("Write")`, `setRightButton("Verify")`
5. Extract and display tag info from infos bundle

---

## 5. Progress Bar Messages

| Phase     | Message              | resources key   | Display                |
|-----------|----------------------|-----------------|------------------------|
| Writing   | Writing...           | `'writing'`     | "Writing..."           |
| Verifying | Verifying...         | `'verifying'`   | "Verifying..."         |

---

## 6. Toast Messages

| Outcome          | Message                          | resources key            | Icon      |
|------------------|----------------------------------|--------------------------|-----------|
| Write success    | Write successful!                | `'write_success'`        | checkmark |
| Write failure    | Write failed!                    | `'write_failed'`         | X         |
| Verify success   | Verification successful!         | `'verify_success'`       | checkmark |
| Verify failure   | Verification failed!             | `'verify_failed'`        | X         |
| Write+Verify     | Write and Verify successful!     | `'write_verify_success'` | checkmark |

---

## 7. Activity Flow Diagram

```
ReadActivity (success)
    |
    | M2/OK (Write button)
    v
WarningWriteActivity
    |
    | Title: "Data ready!"
    | Content: tag type, UID, "Please place new tag"
    | M1="Cancel", M2="Write"
    |
    +-- M1/PWR: finish() (cancel)
    |
    +-- M2/OK: confirm write
         |
         v
    WriteActivity
         |
         | Title: "Write Tag"
         | Shows tag info from infos bundle
         | M1="Write", M2="Verify"
         |
         +-- M1/OK: startWrite()
         |     |
         |     v
         |   WRITING state
         |     |  "Writing..." progress bar
         |     |  All buttons disabled
         |     |
         |     +-- Success: "Write successful!" toast
         |     |     M1(left)="Verify", M2(right)="Rewrite"
         |     |
         |     +-- Failure: "Write failed!" toast
         |           M1(left)="Verify", M2(right)="Rewrite"
         |
         +-- M2: startVerify()
         |     |
         |     v
         |   VERIFYING state
         |     |  "Verifying..." progress bar
         |     |  All buttons disabled
         |     |
         |     +-- Success: "Verification successful!" toast
         |     |     M1(left)="Verify", M2(right)="Rewrite"
         |     |
         |     +-- Failure: "Verification failed!" toast
         |           M1(left)="Verify", M2(right)="Rewrite"
         |
         +-- PWR: finish() (exit at any time)
```

---

## 8. Tag Info Display in WriteActivity

The tag info display format in WriteActivity is identical to ReadActivity (see 05_read_tag/README.md Section 9).

**Evidence**: `Step - 4.png` shows the same format:
```
MIFARE
M1 S50 1K (4B)
Frequency: 13.56MHZ
UID: 2CADC272
SAK: 08  ATQA: 0004
```

---

## 9. Cross-References

| From                  | To                    | Trigger           | Bundle                    |
|-----------------------|-----------------------|--------------------|---------------------------|
| ReadActivity          | WarningWriteActivity  | M2/OK after read   | `{infos: read_data}`      |
| AutoCopyActivity      | WarningWriteActivity  | Internal flow      | `{infos: scan+read_data}` |
| CardWalletActivity    | WarningWriteActivity  | Select dump file   | `{infos: dump_data}`      |
| WarningWriteActivity  | WriteActivity         | M2/OK confirm      | `{infos: tag_data}`       |
| WriteActivity         | (exits to caller)     | PWR                | None                      |

---

## 10. Framebuffer Capture Evidence Index

| Capture File           | State Shown                           | Key Observations                     |
|------------------------|---------------------------------------|--------------------------------------|
| `Step - 3.png`         | WarningWriteActivity (Data ready!)    | Title "Data ready!", "Watch"/"Write" buttons, TYPE: M1-4b |
| `Step - 4.png`         | WriteActivity WRITING                 | Title "Write Tag", "Writing..." progress bar, tag info |
| `Step - 5.png`         | WriteActivity WRITE_FAILED            | "Write failed!" toast with X, "Verify"/"Rewrite" buttons |
| `Step - 2.png`         | ReadActivity READ_SUCCESS (Auto Copy) | "Read Successful! File Saved" toast, "Reread"/"Write" |
| `write_tag_write_failed.png` | WriteActivity WRITE_FAILED | "Write failed!" toast with X, M1="Verify", M2="Rewrite" |

---

## Corrections Applied

1. **Button order self-contradiction removed**: The doc previously stated write failure buttons were "the OPPOSITE order from write success." This was incorrect. Both success and failure show the SAME button order: M1="Verify" (left), M2="Rewrite" (right). Citations: `write_tag_write_failed.png` (failure) and `autocopy_mf1k_gen1a/0800.png` (success) both show identical M1="Verify", M2="Rewrite".
