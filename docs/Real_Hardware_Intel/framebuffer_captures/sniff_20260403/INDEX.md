# Sniff Flow — Real Device Framebuffer Capture

**Date**: 2026-04-03
**Method**: /dev/fb1 RGB565 at 500ms intervals, 458 frames → 61 unique states
**Device**: iCopy-X real hardware, firmware v1.0.90

---

## Flow 1: 14A Sniff with Trace Data (TraceLen: 9945) + Save

| State | Screenshot | Description |
|-------|-----------|-------------|
| 005 | sniff_14a_type_list.png | TYPE_SELECT: "Sniff TRF 1/1", 5 items, no softkeys |
| 006 | sniff_14a_instruction_step1.png | INSTRUCTION: "Sniff TRF 1/4", Step 1 text, M1="Start" M2="Finish" |
| 007 | sniff_14a_instruction_step2.png | INSTRUCTION: "Sniff TRF 2/4", Step 2: "Remove antenna cover..." |
| 008 | sniff_14a_instruction_step3.png | INSTRUCTION: "Sniff TRF 3/4", Step 3: "Swipe tag on iCopy..." |
| 009 | sniff_14a_instruction_step4.png | INSTRUCTION: "Sniff TRF 4/4", Step 4: "Repeat 3-5 times..." |
| 011 | sniff_14a_sniffing_in_progress.png | SNIFFING: "Sniffing in progress..." toast over Step 1, M1="Start" M2="Finish" |
| 013 | sniff_14a_loading_progressbar.png | LOADING: empty content area with grey progress bar at bottom, no buttons |
| 014 | sniff_14a_decoding_288_of_9945.png | DECODING: "TraceLen: 9945" top, "Decoding... 288/9945" blue text, blue progress bar |
| 020 | sniff_14a_decoding_3204_of_9945.png | DECODING: progress at 3204/9945, bar ~30% filled |
| 030 | sniff_14a_result_tracelen_9945.png | RESULT: "TraceLen: 9945" centered, M1="Start" M2="Save" |
| 031 | sniff_14a_processing_toast.png | PROCESSING: "Processing..." toast overlay (after M2=Save pressed) |
| 032 | sniff_14a_trace_file_saved.png | SAVE TOAST: "Trace file saved" toast over TraceLen display |
| 034 | sniff_14a_result_after_save_dimmed.png | RESULT: TraceLen: 9945, M2="Save" dimmed (already saved) |

### Key UI observations — 14A flow

1. **DECODING state** is a distinct visual state: "TraceLen: N" at top, "Decoding... X/N" in blue text, blue progress bar below
2. **No softkeys during LOADING/DECODING** — buttons only appear after decoding completes
3. **"Processing..." toast** appears when Save is pressed — distinct from "Sniffing in progress..." toast
4. **M2="Save" dims after save** — indicates save completed, button becomes inactive
5. **Progress bar** is blue fill on grey track, positioned at bottom of content area

---

## Flow 2: T5577 Sniff (TraceLen: 42259) + Save

| State | Screenshot | Description |
|-------|-----------|-------------|
| 038 | sniff_t5577_type_selected.png | TYPE_SELECT: T5577 highlighted (item 5) |
| 039 | sniff_t5577_instruction.png | INSTRUCTION: "Sniff TRF 1/1", single page T5577 text, M1="Start" M2="Finish" |
| 040 | sniff_t5577_sniffing_in_progress.png | SNIFFING: "Sniffing in progress..." toast over T5577 instruction |
| 041 | sniff_t5577_result_empty.png | RESULT: empty content, M1="Start" M2="Save" (before trace parsed) |
| 042 | sniff_t5577_result_tracelen_42259.png | RESULT: "TraceLen: 42259", M1="Start" M2="Save" |
| 043 | sniff_t5577_processing_toast.png | PROCESSING: "Processing..." toast (after Save) |
| 044 | sniff_t5577_trace_file_saved.png | SAVE TOAST: "Trace file saved" over TraceLen display |
| 045 | sniff_t5577_result_after_save.png | RESULT: TraceLen: 42259, M2="Save" dimmed |

### Key UI observations — T5577 flow

1. **Title stays "Sniff TRF 1/1"** throughout — T5577 has single instruction page (no 1/4 pagination)
2. **No DECODING phase** for T5577 — goes directly from sniffing to result
3. **TraceLen: 42259** — LF trace is much larger than HF (42KB vs 10KB)
4. **Same "Processing..." + "Trace file saved" toast sequence** as HF

---

## Flow 3: 14A Empty Sniff (TraceLen: 0)

| State | Screenshot | Description |
|-------|-----------|-------------|
| 057 | sniff_14a_empty_instruction_step1.png | INSTRUCTION: Step 1 (same as Flow 1) |
| 058 | sniff_14a_empty_sniffing_in_progress.png | SNIFFING: toast overlay (same as Flow 1) |
| 059 | sniff_14a_empty_result_tracelen_0.png | RESULT: "TraceLen: 0", M1="Start" M2="Save" |

### Key UI observations — Empty trace

1. **"TraceLen: 0"** displayed (NOT blank) — our current tests were correct on this
2. **No DECODING phase** when trace is empty — goes directly to result
3. **Save button still available** even with empty trace

---

## Complete State Machine (from FB captures)

```
TYPE_SELECT: "Sniff TRF 1/1", 5 items, no softkeys
    ↓ OK
INSTRUCTION: "Sniff TRF N/4" (HF) or "1/1" (T5577), M1="Start" M2="Finish"
    ↓ M1
SNIFFING: "Sniffing in progress..." toast, M1="Start" M2="Finish"
    ↓ M2 (or auto-stop for T5577)
LOADING: grey progress bar, no text, no buttons (transient, HF only)
    ↓ (automatic)
DECODING: "TraceLen: N" + "Decoding... X/N" + blue progress bar (HF only, if trace > 0)
    ↓ (automatic)
RESULT: "TraceLen: N" centered, M1="Start" M2="Save"
    ↓ M2
PROCESSING: "Processing..." toast (save in progress)
    ↓ (automatic)
SAVE_DONE: "Trace file saved" toast, M2="Save" dimmed
    ↓ PWR
TYPE_SELECT (or main menu)
```

## Missing from our current implementation

1. **LOADING state** (state_013): grey progress bar with no text — appears between sniffing and decoding
2. **DECODING state** (states 014-029): "Decoding... X/N" with blue progress bar — real-time progress
3. **"Processing..." toast** (states 031, 043): appears when Save is pressed, before "Trace file saved"
4. **TraceLen shows actual data** (9945, 42259) — our tests show 0 because fixtures don't populate trace length
5. **M2="Save" dims after save** — indicates save completed
