#!/usr/bin/env python3
"""Extract legacy PM3 firmware output catalog from Real_Hardware_Intel traces.

Produces /home/qx/icopy-x-reimpl/tools/ground_truth/legacy_output.json.

Scope: top-level .txt files whose names do NOT contain 'iceman' (case-insensitive).

Handles two PM3 line formats:
    [<ts>] PM3> <full_cmd> [(timeout=N[, listener=None])]
    [<ts>] PM3< ret=<N> <body>
    [<ts>] [TThread-X] PM3> <full_cmd> (timeout=N[, listener=None])
    [<ts>] [TThread-X] PM3< ret=<N> listener_calls=<N> cache=<body>

Body quirks (all handled):
 * Leading 'content_len=NNN ' / 'len=NNN ' token before body (strip).
 * Body may begin with '[usb|script] pm3 --> <cmd>' echo — strip echo line.
 * Body may end with 'Nikola.D: <n>' sentinel — strip sentinel.
 * Literal '\\n' escapes preserved in raw_body.
 * Multi-line bodies (real newlines) collected until next event line.
 * Severity prefixes [+], [=], [-], [!], [|], [\\], [/] preserved.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/qx/icopy-x-reimpl/docs/Real_Hardware_Intel")
OUT = Path("/home/qx/icopy-x-reimpl/tools/ground_truth/legacy_output.json")

# --- line-level regexes -----------------------------------------------------
# Timestamp: e.g. "[   56.944]" or "[-1770640930.371]" — allow optional minus and spaces.
_TS = r"\[\s*-?\d+\.\d+\]"
# Optional thread tag: "[TThread-1]"
_TAG = r"(?:\s*\[[^]]+\])?"

CMD_LINE = re.compile(
    rf"^{_TS}{_TAG}\s+PM3>\s+(?P<cmd>.+?)$"
)
RSP_LINE = re.compile(
    rf"^{_TS}{_TAG}\s+PM3<\s+ret=(?P<ret>-?\d+)(?:\s+(?P<rest>.*))?$"
)
TS_EXTRACT = re.compile(r"\[\s*(-?\d+\.\d+)\]")

# Alternative wall-clock trace format (trace_autocopy_mf1k_standard, trace_erase_gen1a_and_standard):
#   [HH:MM:SS] PM3_CMD: <cmd>
#   [HH:MM:SS] PM3_RET: <ret> (<time>s) cache=<N> bytes
#   [HH:MM:SS] PM3_CACHE: '<body>'   (or "<body>")
WALLCLOCK_TS = r"\[\d{2}:\d{2}:\d{2}\]"
CMD_LINE_WC = re.compile(rf"^\s*{WALLCLOCK_TS}\s+PM3_CMD:\s+(?P<cmd>.+?)$")
RSP_LINE_WC = re.compile(rf"^\s*{WALLCLOCK_TS}\s+PM3_RET:\s+(?P<ret>-?\d+)\s+\([^)]*\)\s*(?:cache=(?P<cache>\d+)\s+bytes)?\s*$")
CACHE_LINE_WC = re.compile(rf"^\s*{WALLCLOCK_TS}\s+PM3_CACHE:\s+(?P<body>.*)$")
WC_TS_EXTRACT = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]")

# Any line that begins with a timestamp and is NOT a PM3 data line — boundary for multi-line bodies.
EVENT_LINE = re.compile(rf"^{_TS}{_TAG}\s+(?:PM3[<>]|KEY>|START|FINISH|POLL|CACHE:|SERIAL_TX>|REWORK[<>]|\[TThread|===|sitecustomize|application|installing|imports|pm3_compat|not app|processor|\w)")
# We only need: does line start with "[<ts>]" and look like a new event?
NEW_EVENT_START = re.compile(rf"^{_TS}")


def strip_echo_and_sentinel(body: str) -> tuple[str, str | None]:
    """Handle the older '[usb|script] pm3 --> <cmd>\\n\\n<body>\\n\\nNikola.D: <n>\\n' wrap.
    Returns (cleaned_body, echoed_command_or_None). Preserves literal backslash-n escapes.
    """
    echoed: str | None = None
    stripped = body
    if stripped.startswith("[usb|script] pm3 --> "):
        prefix_len = len("[usb|script] pm3 --> ")
        # Echo runs until the FIRST literal "\n" or real newline after the prefix.
        idx_literal = stripped.find("\\n", prefix_len)
        idx_real = stripped.find("\n", prefix_len)
        candidates = [i for i in (idx_literal, idx_real) if i != -1]
        if candidates:
            cut = min(candidates)
            echoed = stripped[prefix_len:cut].strip()
            if stripped[cut:cut + 2] == "\\n":
                stripped = stripped[cut + 2:]
            else:
                stripped = stripped[cut + 1:]
        else:
            echoed = stripped[prefix_len:].strip()
            stripped = ""
    # Strip trailing Nikola.D sentinel — either "\nNikola.D: N\n" or "\n\nNikola.D: N\n"
    m = re.search(r"(?:\\n|\n)Nikola\.D:\s+-?\d+(?:\\n|\n)?\s*$", stripped)
    if m:
        stripped = stripped[:m.start()]
    return stripped, echoed


def strip_len_prefix(rest: str) -> str:
    """Strip leading 'content_len=N ' / 'len=N ' / 'listener_calls=N cache=' tokens."""
    if rest.startswith("content_len="):
        m = re.match(r"content_len=\d+\s+(.*)$", rest, re.S)
        if m:
            return m.group(1)
    if rest.startswith("len="):
        m = re.match(r"len=\d+\s+(.*)$", rest, re.S)
        if m:
            return m.group(1)
    if rest.startswith("listener_calls="):
        # e.g. "listener_calls=0 cache=<body>"
        m = re.match(r"listener_calls=\d+\s+cache=(.*)$", rest, re.S)
        if m:
            return m.group(1)
    return rest


def compute_prefix(cmd: str) -> str:
    """Strip leading command down to first variable arg (numeric, hex, flag, filename).

    PM3 subcommand tokens often contain digits (e.g. '14a', '15', '4x05_info',
    '410x_write', '1090'). We only treat a token as variable when it is a
    pure decimal integer, a pure hex literal of length >= 4, a flag, or a path.
    """
    # Strip any trailing " (timeout=...)" metadata first.
    cmd = re.sub(r"\s*\(timeout=.*\)\s*$", "", cmd).strip()
    parts = cmd.split()
    kept: list[str] = []
    for p in parts:
        if not p:
            continue
        # Stop on first flag
        if p.startswith("-") and len(p) > 1:
            break
        # Stop on first pure decimal integer (payload: block/sector/offset).
        if re.fullmatch(r"-?\d+", p):
            break
        # Stop on first pure hex literal of length >= 4 (payloads: UIDs, keys, data).
        if re.fullmatch(r"[0-9a-fA-F]{4,}", p):
            break
        # Stop on path/filename
        if "/" in p or p.startswith(".") or p.endswith(".dic") or p.endswith(".bin") or p.endswith(".eml") or p.endswith(".pm3") or p.endswith(".json"):
            break
        # Stop on single-char A/B key selector (MIFARE).
        if p in ("A", "B", "a", "b") and kept:
            break
        kept.append(p)
    if not kept:
        # Fallback to first token.
        return parts[0] if parts else cmd
    return " ".join(kept)


def canonicalize_shape(body: str) -> str:
    """Return a shape signature: replace every hex/numeric run with 'X' placeholder,
    preserving whitespace, punctuation, and structural text.
    Two bodies share a shape iff their canonicalized signatures are identical."""
    # Preserve literal "\\n" as itself (they are separators, not digits).
    # Replace runs of hex (case-insensitive, 2+ chars) that look like payloads.
    # Strategy: tokenize. But simpler: apply regex substitutions.
    # 1) Replace hex sequences of length >= 2 containing at least one digit OR pure hex >= 4.
    # 2) Replace standalone integers.
    sig = body
    # 32-bit hex words (0x....) first.
    sig = re.sub(r"0x[0-9a-fA-F]+", "0xX", sig)
    # Runs of hex-pair blocks separated by spaces or colons (UIDs, data dumps)
    sig = re.sub(r"\b[0-9a-fA-F]{2,}\b", "H", sig)
    # Pure signed integers (e.g. counts)
    sig = re.sub(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?", "N", sig)
    return sig


# --- parse per file ---------------------------------------------------------

def unquote_python_literal(s: str) -> tuple[str, bool]:
    """Unwrap a Python-repr string: '...' or "..." — keep content verbatim, don't interpret escapes.
    Returns (unquoted, was_quoted)."""
    s = s.strip()
    if len(s) >= 2 and s[0] in ("'", '"') and s[-1] == s[0]:
        return s[1:-1], True
    return s, False


def parse_file_wallclock(path: Path, text: str) -> tuple[list[dict], list[dict]]:
    """Parse the [HH:MM:SS] PM3_CMD/PM3_RET/PM3_CACHE format."""
    samples: list[dict] = []
    anomalies: list[dict] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    pending_cmd: str | None = None
    pending_ts: str | None = None
    while i < n:
        line = lines[i]
        m_cmd = CMD_LINE_WC.match(line)
        m_ret = RSP_LINE_WC.match(line)
        m_cache = CACHE_LINE_WC.match(line)
        if m_cmd:
            if pending_cmd is not None:
                anomalies.append({
                    "file": path.name,
                    "timestamp": pending_ts or "",
                    "issue": "command with no response (wallclock)",
                    "line": pending_cmd[:200],
                })
            pending_cmd = m_cmd.group("cmd").strip()
            pending_cmd = re.sub(r"\s*\(timeout=.*\)\s*$", "", pending_cmd).strip()
            ts_m = WC_TS_EXTRACT.search(line)
            pending_ts = ts_m.group(1) if ts_m else ""
            i += 1
            continue
        if m_ret:
            ret_str = m_ret.group("ret")
            # Look ahead for the matching PM3_CACHE line.
            body = ""
            truncated = False
            if i + 1 < n:
                m2 = CACHE_LINE_WC.match(lines[i + 1])
                if m2:
                    raw = m2.group("body")
                    # Handle multi-line bodies: if the Python-literal quote isn't closed on this line,
                    # accumulate lines until a balanced quote is found (rare but possible).
                    unq, ok = unquote_python_literal(raw)
                    body = unq
                    if not ok and raw:
                        body = raw
                    # Truncation heuristic (body ends mid-word).
                    if body and body[-1].isalnum() and len(body) >= 200:
                        truncated = True
                    i += 1  # consume cache line.
                # If no cache line, body stays empty.
            try:
                ret_int = int(ret_str)
            except ValueError:
                anomalies.append({
                    "file": path.name,
                    "timestamp": "",
                    "issue": f"unparseable ret={ret_str!r} (wallclock)",
                    "line": line[:200],
                })
                i += 1
                continue
            if pending_cmd is None:
                anomalies.append({
                    "file": path.name,
                    "timestamp": "",
                    "issue": "response without preceding command (wallclock)",
                    "line": line[:200],
                })
                i += 1
                continue
            ts_m = WC_TS_EXTRACT.search(line)
            ts = ts_m.group(1) if ts_m else ""
            samples.append({
                "source_file": path.name,
                "timestamp": ts,
                "full_command": pending_cmd,
                "ret": ret_int,
                "raw_body": body,
                "truncated": truncated,
            })
            pending_cmd = None
            pending_ts = None
            i += 1
            continue
        i += 1
    if pending_cmd is not None:
        anomalies.append({
            "file": path.name,
            "timestamp": pending_ts or "",
            "issue": "command with no response (wallclock, end of file)",
            "line": pending_cmd[:200],
        })
    return samples, anomalies


def parse_file(path: Path) -> tuple[list[dict], list[dict]]:
    """Return (samples, anomalies).
    Each sample: {source_file, timestamp, full_command, ret, raw_body, truncated}.
    Each anomaly: {file, timestamp, issue, line (excerpt)}.
    """
    samples: list[dict] = []
    anomalies: list[dict] = []

    try:
        text = path.read_text(errors="replace")
        lines = text.splitlines(keepends=False)
    except Exception as e:  # pragma: no cover
        anomalies.append({"file": path.name, "timestamp": "", "issue": f"unreadable: {e}", "line": ""})
        return samples, anomalies

    # Route to wallclock parser if the file uses that format.
    if "PM3_CMD:" in text and "PM3_CACHE:" in text:
        return parse_file_wallclock(path, text)

    # Pending command awaiting response.
    pending_cmd: str | None = None
    pending_ts: str | None = None

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m_cmd = CMD_LINE.match(line)
        m_rsp = RSP_LINE.match(line)
        if m_cmd:
            # A new command line. Any unresolved pending command becomes an orphan (no response).
            if pending_cmd is not None:
                anomalies.append({
                    "file": path.name,
                    "timestamp": pending_ts or "",
                    "issue": "command with no response",
                    "line": pending_cmd[:200],
                })
            pending_cmd = m_cmd.group("cmd").strip()
            # Strip trailing "(timeout=...)" meta from command (keep meta out of prefix, but log full).
            pending_cmd = re.sub(r"\s*\(timeout=.*\)\s*$", "", pending_cmd).strip()
            ts_m = TS_EXTRACT.match(line)
            pending_ts = ts_m.group(1) if ts_m else ""
            i += 1
            continue
        if m_rsp:
            ret_str = m_rsp.group("ret")
            rest = m_rsp.group("rest") or ""
            rest = strip_len_prefix(rest)
            # Multi-line body? If the next line also starts with a timestamp-ish event, this is a single-line body.
            # If not, consume continuation lines until we hit a new "[<ts>]" event line or EOF.
            body_lines = [rest]
            j = i + 1
            while j < n:
                nxt = lines[j]
                if NEW_EVENT_START.match(nxt):
                    break
                body_lines.append(nxt)
                j += 1
            # Recombine body lines with REAL newlines to preserve multi-line structure.
            raw_body = "\n".join(body_lines).rstrip("\n")
            # Now unwrap old [usb|script] echo + Nikola.D sentinel.
            unwrapped, echoed_cmd = strip_echo_and_sentinel(raw_body)
            # Truncation heuristic: body ends mid-token without closing newline context and
            # length looks suspiciously capped (older traces seemingly cut at ~255 chars sometimes).
            truncated = False
            if unwrapped and not unwrapped.endswith(("\\n", "\n")):
                # Not conclusive. Only flag if final char is not punctuation/space AND body >= 200 chars.
                if len(unwrapped) >= 200 and unwrapped[-1].isalnum():
                    truncated = True
            ts_m = TS_EXTRACT.match(line)
            ts = ts_m.group(1) if ts_m else ""
            try:
                ret_int = int(ret_str)
            except ValueError:
                anomalies.append({
                    "file": path.name,
                    "timestamp": ts,
                    "issue": f"unparseable ret={ret_str!r}",
                    "line": line[:200],
                })
                i = j
                continue
            if pending_cmd is None and echoed_cmd is None:
                anomalies.append({
                    "file": path.name,
                    "timestamp": ts,
                    "issue": "response without preceding command",
                    "line": line[:200],
                })
                i = j
                continue
            # Prefer echoed command when legacy wrap is present — that's the authoritative
            # command the firmware actually ran (responses can be interleaved).
            effective_cmd = echoed_cmd if echoed_cmd else pending_cmd
            # Sanity-check: note any mismatch between issued and echoed cmd.
            if echoed_cmd and pending_cmd and echoed_cmd != pending_cmd:
                anomalies.append({
                    "file": path.name,
                    "timestamp": ts,
                    "issue": f"echo/pending mismatch: pending={pending_cmd!r} echo={echoed_cmd!r}",
                    "line": line[:200],
                })
            samples.append({
                "source_file": path.name,
                "timestamp": ts,
                "full_command": effective_cmd or "",
                "ret": ret_int,
                "raw_body": unwrapped,
                "truncated": truncated,
            })
            pending_cmd = None
            pending_ts = None
            i = j
            continue
        i += 1

    if pending_cmd is not None:
        anomalies.append({
            "file": path.name,
            "timestamp": pending_ts or "",
            "issue": "command with no response (end of file)",
            "line": pending_cmd[:200],
        })

    return samples, anomalies


# --- main -------------------------------------------------------------------

def main() -> int:
    txt_files = sorted(p for p in ROOT.glob("*.txt") if "iceman" not in p.name.lower())
    print(f"Processing {len(txt_files)} non-iceman .txt files", file=sys.stderr)
    for f in txt_files:
        print(f"  - {f.name}", file=sys.stderr)

    all_samples: list[dict] = []
    all_anomalies: list[dict] = []

    for p in txt_files:
        samples, anomalies = parse_file(p)
        all_samples.extend(samples)
        all_anomalies.extend(anomalies)
        print(f"  [{p.name}] {len(samples)} samples, {len(anomalies)} anomalies", file=sys.stderr)

    # Group by prefix.
    grouped: dict[str, list[dict]] = defaultdict(list)
    for s in all_samples:
        prefix = compute_prefix(s["full_command"])
        grouped[prefix].append(s)

    commands: dict[str, dict] = {}
    for prefix in sorted(grouped.keys()):
        samples = grouped[prefix]
        # Distinct full commands.
        full_cmds = sorted({s["full_command"] for s in samples})
        # Shape analysis.
        shape_index: dict[str, dict] = OrderedDict()
        next_id = 1
        for s in samples:
            sig = canonicalize_shape(s["raw_body"])
            bucket = shape_index.get(sig)
            if bucket is None:
                bucket = {
                    "shape_id": next_id,
                    "example_body": s["raw_body"],
                    "occurrence_count": 0,
                    "source_files": [],
                }
                shape_index[sig] = bucket
                next_id += 1
            bucket["occurrence_count"] += 1
            if s["source_file"] not in bucket["source_files"]:
                bucket["source_files"].append(s["source_file"])
        distinct_shapes = []
        for sig, b in shape_index.items():
            distinct_shapes.append({
                "shape_id": b["shape_id"],
                "example_body": b["example_body"],
                "occurrence_count": b["occurrence_count"],
                "source_files": sorted(b["source_files"]),
            })
        # Sort shapes by occurrence desc, then shape_id asc.
        distinct_shapes.sort(key=lambda x: (-x["occurrence_count"], x["shape_id"]))
        commands[prefix] = {
            "prefix": prefix,
            "full_command_samples": full_cmds,
            "response_count": len(samples),
            "response_samples": [
                {
                    "source_file": s["source_file"],
                    "timestamp": s["timestamp"],
                    "full_command": s["full_command"],
                    "ret": s["ret"],
                    "raw_body": s["raw_body"],
                    "truncated": s["truncated"],
                }
                for s in samples
            ],
            "distinct_response_shapes": distinct_shapes,
        }

    out = {
        "metadata": {
            "firmware": "legacy",
            "files_processed": len(txt_files),
            "files_list": [p.name for p in txt_files],
            "total_samples": len(all_samples),
            "distinct_command_prefixes": len(commands),
            "extraction_date": datetime.now(timezone.utc).isoformat(),
        },
        "commands": commands,
        "anomalies": all_anomalies,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    # Validate.
    with OUT.open() as fh:
        json.load(fh)
    print(f"OK wrote {OUT} ({OUT.stat().st_size} bytes)", file=sys.stderr)

    # Summary stats for the human.
    prefix_counts = [(k, v["response_count"]) for k, v in commands.items()]
    prefix_counts.sort(key=lambda x: -x[1])
    print("\nTop 10 prefixes by frequency:", file=sys.stderr)
    for k, c in prefix_counts[:10]:
        n_shapes = len(commands[k]["distinct_response_shapes"])
        print(f"  {c:5d}  {k:40s} shapes={n_shapes}", file=sys.stderr)

    # Shape count distribution.
    shape_hist = Counter(len(v["distinct_response_shapes"]) for v in commands.values())
    print(f"\nShape count histogram (count_of_shapes: num_prefixes):", file=sys.stderr)
    for k in sorted(shape_hist.keys()):
        print(f"  {k:4d}: {shape_hist[k]}", file=sys.stderr)

    print(f"\nTotals: files={len(txt_files)} samples={len(all_samples)} prefixes={len(commands)} anomalies={len(all_anomalies)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
