#!/usr/bin/env python3
"""Extractor B: ICEMAN firmware ground-truth cataloguer.

Processes iceman trace files in docs/Real_Hardware_Intel/ and produces
iceman_output.json with per-command-prefix response catalogue.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

TRACE_DIR = Path("/home/qx/icopy-x-reimpl/docs/Real_Hardware_Intel")
OUT_FILE = Path("/home/qx/icopy-x-reimpl/tools/ground_truth/iceman_output.json")

# Regexes
CMD_RE = re.compile(r"^\[\s*([0-9.]+)\]\s+PM3>\s+(.*)$")
# accepts:
#   PM3< ret=N
#   PM3< ret=N content_len=M <body>
#   PM3< ret=N len=M <body>
RESP_RE = re.compile(
    r"^\[\s*([0-9.]+)\]\s+PM3<\s+ret=(-?\d+)(?:\s+(?:content_len|len)=(\d+))?(?:\s(.*))?$"
)


def list_iceman_files() -> list[Path]:
    files: list[Path] = []
    for p in sorted(TRACE_DIR.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".txt":
            continue
        if "iceman" not in p.name.lower():
            continue
        files.append(p)
    return files


def strip_timeout(cmd: str) -> tuple[str, str | None]:
    """Strip trailing `(timeout=NNN)` from command; return (cmd, raw_full_cmd)."""
    # Preserve the original full command text (without timestamp)
    full = cmd
    m = re.match(r"^(.*?)\s*\(timeout=(-?\d+)\)\s*$", cmd)
    if m:
        return m.group(1).strip(), full
    return cmd.strip(), full


def unwrap_body(body: str) -> tuple[str, bool]:
    """Detect and strip older wrapper: `[usb|script] pm3 --> <cmd>\\n\\n<body>\\n\\nNikola.D: <n>\\n`.

    Returns (body_without_wrapper, was_wrapped).

    NOTE: body is the raw body text as read from the log line, where \\n is a
    literal two-character escape (backslash + n), NOT a newline byte.
    """
    if body is None:
        return "", False
    original = body

    # Quote-stripping: the 20260416 traces wrap body in ' or "
    if len(body) >= 2 and body[0] in "\"'" and body[-1] == body[0]:
        body = body[1:-1]

    # Trim Nikola.D trailer if present.
    # Pattern variants seen:
    #   "<body>\nNikola.D: -10\n"
    #   "...\n\nNikola.D: 0\n"
    nk = re.search(r"\\nNikola\.D:\s*-?\d+\\n\s*$", body)
    if nk:
        body = body[: nk.start()]

    # Trim trailing `pm3 -->` prompt if present.
    # Patterns:
    #   "...\n\npm3 -->\n"
    pp = re.search(r"(?:\\n)*pm3\s*-->\s*(?:\\n)*$", body)
    if pp:
        body = body[: pp.start()]

    return body, body != original


def _token_is_value(t: str) -> bool:
    """True if token t looks like a variable argument (flag, path, decimal, long hex)."""
    if t.startswith("-"):
        return True
    if "/" in t:
        return True
    # Filename-like (name.ext, but NOT `4x05_info` which has no dot)
    if re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9]+", t):
        return True
    # Pure decimal: single digits (block numbers) OR multi-digit values
    if re.fullmatch(r"\d+", t):
        return True
    # Single-letter key indicator: A, B, a, b (MIFARE key type literal) — value, not subcommand
    if re.fullmatch(r"[ABab]", t):
        return True
    # Long hex (>=4 hex chars with at least one digit) — e.g. 0AD07AB8, 484558414354
    if re.fullmatch(r"[0-9A-Fa-f]{4,}", t) and re.search(r"\d", t):
        return True
    # All-hex-letter strings >=8 chars (e.g. FFFFFFFF, DEADBEEF) — still value
    if re.fullmatch(r"[A-Fa-f]{8,}", t):
        return True
    return False


def prefix_of(cmd: str) -> str:
    """Derive command prefix: stop at the first variable-argument token.

    PM3 subcommand tokens (like `14a`, `15`, `410x`, `4x05_info`) are kept
    because they identify the command branch. A token is treated as a value
    (and thus stops the prefix) when it matches `_token_is_value`.
    """
    tokens = cmd.split()
    prefix_tokens: list[str] = []
    for idx, t in enumerate(tokens):
        # Position 0-1: always subcommand (hf, lf, data, hw, mem, reveng, script, trace, ...)
        if idx < 2:
            prefix_tokens.append(t)
            continue
        if _token_is_value(t):
            break
        prefix_tokens.append(t)
    if not prefix_tokens:
        return cmd.strip()
    return " ".join(prefix_tokens)


def shape_of(body: str) -> str:
    """Normalise body for shape grouping: replace numeric/hex literals with placeholders.

    Whitespace and line ordering must be preserved; only numeric/hex payload
    values are collapsed. Pure decimal and pure hex values collapse to the
    same placeholder `<N>` so that tokens like `60`, `4`, `AFA785A7DAB33378`,
    `2020666666668888` all group together (they differ only in value, not
    shape).
    """
    if body is None:
        return ""
    s = body
    # Order matters: longer/hex-runs first so we don't half-match.
    # Hex byte runs like "AB CD EF 12" -> "<HEXSEQ>" (preserve spacing otherwise).
    s = re.sub(r"\b[0-9A-Fa-f]{2}(?:[ :][0-9A-Fa-f]{2})+\b", "<HEXSEQ>", s)
    # Standalone hex tokens >= 4 chars (regardless of which hex chars) — true
    # hex payloads (keys, UIDs, passwords). Use <N> so that differing values
    # don't split shapes.
    s = re.sub(r"\b[0-9A-Fa-f]{4,}\b", "<N>", s)
    # Remaining pure decimal runs (>=1 digit).
    s = re.sub(r"\b\d+\b", "<N>", s)
    return s


def parse_file(path: Path, anomalies: list[dict]) -> list[dict]:
    """Return list of (cmd_record, timestamp, ret, body, truncated, full_command) dicts."""
    records: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as e:
        anomalies.append(
            {"file": path.name, "timestamp": None, "issue": f"read error: {e}"}
        )
        return records

    pending: dict | None = None  # the most recent PM3> awaiting its PM3<

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        m_cmd = CMD_RE.match(line)
        if m_cmd:
            ts = m_cmd.group(1).strip()
            rest = m_cmd.group(2)
            cmd_core, full_command = strip_timeout(rest)
            if pending is not None:
                # Previous command had no response before this new command — orphan.
                anomalies.append(
                    {
                        "file": path.name,
                        "timestamp": pending["timestamp"],
                        "issue": f"PM3> command '{pending['full_command']}' had no matching PM3< before next command",
                    }
                )
            pending = {
                "timestamp": ts,
                "full_command": full_command,
                "cmd_core": cmd_core,
                "lineno": lineno,
            }
            continue

        m_resp = RESP_RE.match(line)
        if m_resp:
            ts = m_resp.group(1).strip()
            ret = int(m_resp.group(2))
            declared_len_s = m_resp.group(3)
            body = m_resp.group(4) or ""
            declared_len = int(declared_len_s) if declared_len_s is not None else None

            # Unwrap older wrapper (pm3 -->, Nikola.D, outer quotes)
            body_unwrapped, _ = unwrap_body(body)
            # Detect truncation: if body ends in "...(truncated)" or declared_len
            # is larger than what we can measure in literal \n-form.
            truncated = False
            if body_unwrapped.endswith("...(truncated)"):
                truncated = True
            # Heuristic truncation on trailing quote mismatch
            if body.endswith("...'") or body.endswith("...\""):
                truncated = True

            if pending is None:
                anomalies.append(
                    {
                        "file": path.name,
                        "timestamp": ts,
                        "issue": f"PM3< response with no preceding PM3>: raw='{line[:200]}'",
                    }
                )
                continue

            rec = {
                "source_file": path.name,
                "timestamp": pending["timestamp"],
                "response_timestamp": ts,
                "full_command": pending["full_command"],
                "cmd_core": pending["cmd_core"],
                "ret": ret,
                "raw_body": body_unwrapped,
                "raw_body_pre_unwrap": body,
                "declared_len": declared_len,
                "truncated": truncated,
            }
            records.append(rec)
            pending = None
            continue

        # Not a command or response line — ignore (SERIAL_TX>, CACHE:, POLL, KEY>, etc.)

    # End-of-file: if pending still exists, it's an orphan command (no response captured).
    if pending is not None:
        anomalies.append(
            {
                "file": path.name,
                "timestamp": pending["timestamp"],
                "issue": f"PM3> command '{pending['full_command']}' had no PM3< response before EOF",
            }
        )

    return records


def main() -> int:
    files = list_iceman_files()
    print(f"[extract] {len(files)} iceman files", file=sys.stderr)
    for f in files:
        print(f"  - {f.name}", file=sys.stderr)

    anomalies: list[dict] = []
    all_records: list[dict] = []
    for f in files:
        recs = parse_file(f, anomalies)
        all_records.extend(recs)

    # Bucket by prefix
    commands: dict[str, dict] = OrderedDict()
    # Per-prefix shape collector
    per_prefix_shapes: dict[str, dict[str, dict]] = defaultdict(dict)
    # Per-prefix full_command samples (deduped, first-seen order, cap 10)
    per_prefix_samples: dict[str, list[str]] = defaultdict(list)

    for r in all_records:
        p = prefix_of(r["cmd_core"])
        entry = commands.setdefault(
            p,
            {
                "prefix": p,
                "full_command_samples": [],
                "response_count": 0,
                "response_samples": [],
                "distinct_response_shapes": [],
            },
        )
        entry["response_count"] += 1

        fc = r["full_command"]
        if fc not in per_prefix_samples[p]:
            per_prefix_samples[p].append(fc)

        # Response sample — cap at 10 per prefix
        if len(entry["response_samples"]) < 10:
            entry["response_samples"].append(
                {
                    "source_file": r["source_file"],
                    "timestamp": r["timestamp"],
                    "full_command": r["full_command"],
                    "ret": r["ret"],
                    "raw_body": r["raw_body"],
                    "truncated": r["truncated"],
                }
            )

        sh = shape_of(r["raw_body"])
        shape_key = f"ret={r['ret']}||{sh}"
        shape_rec = per_prefix_shapes[p].get(shape_key)
        if shape_rec is None:
            shape_rec = {
                "shape_id": len(per_prefix_shapes[p]) + 1,
                "ret": r["ret"],
                "example_body": r["raw_body"],
                "occurrence_count": 0,
                "source_files": [],
            }
            per_prefix_shapes[p][shape_key] = shape_rec
        shape_rec["occurrence_count"] += 1
        if r["source_file"] not in shape_rec["source_files"]:
            shape_rec["source_files"].append(r["source_file"])

    # Finalise — populate full_command_samples (cap 10) and distinct_response_shapes.
    for p, entry in commands.items():
        entry["full_command_samples"] = per_prefix_samples[p][:10]
        shapes = list(per_prefix_shapes[p].values())
        # Stable order: by shape_id
        shapes.sort(key=lambda s: s["shape_id"])
        entry["distinct_response_shapes"] = shapes

    out = {
        "metadata": {
            "firmware": "iceman",
            "files_processed": len(files),
            "files_list": [f.name for f in files],
            "total_samples": len(all_records),
            "distinct_command_prefixes": len(commands),
            "extraction_date": dt.datetime.now(dt.timezone.utc).isoformat(),
        },
        "commands": commands,
        "anomalies": anomalies,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    # Summary
    prefixes_by_freq = sorted(commands.items(), key=lambda kv: -kv[1]["response_count"])
    top5 = prefixes_by_freq[:5]
    shape_counts = [len(entry["distinct_response_shapes"]) for entry in commands.values()]
    shape_dist = Counter(shape_counts)
    print("--- Summary ---", file=sys.stderr)
    print(f"Files processed:   {len(files)}", file=sys.stderr)
    print(f"Total samples:     {len(all_records)}", file=sys.stderr)
    print(f"Distinct prefixes: {len(commands)}", file=sys.stderr)
    print(f"Anomalies:         {len(anomalies)}", file=sys.stderr)
    print("Top-5 prefixes by frequency:", file=sys.stderr)
    for prefix, entry in top5:
        print(
            f"  {entry['response_count']:5d}  {prefix}  ({len(entry['distinct_response_shapes'])} shapes)",
            file=sys.stderr,
        )
    print("Shape-count distribution (shapes_per_prefix -> count_of_prefixes):", file=sys.stderr)
    for k in sorted(shape_dist):
        print(f"  {k}: {shape_dist[k]}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
