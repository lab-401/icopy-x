#!/usr/bin/env python3
"""Build the complete PM3 Source Strings reference."""
import json
import os
import re
import sys
from datetime import date

# Import extractor
sys.path.insert(0, '/tmp')
from extract_handler import extract_handler

ICEMAN_ROOT = '/tmp/rrg-pm3/client/src'
LEGACY_ROOT = '/tmp/factory_pm3/client/src'

with open('/tmp/tables.json') as f:
    TABS = json.load(f)


def norm(body):
    """Normalize a PrintAndLogEx body for display (single line)."""
    body = re.sub(r'\s+', ' ', body).strip()
    return body


# Map top-level families -> list of (cmd_family, list-of-subcmd-handlers)
# Walk each cmd*.c that contains a table named like "*Table"/"CommandTable".

def find_subtable(tree, cmd_file, fn_handler):
    """Given a handler function (e.g. 'CmdHFMF'), find the CommandTable in its file."""
    # We can't easily map from CmdHFMF -> cmdhfmf.c without convention.
    # So instead: the *contents* of each cmd*.c file have their own table. Just use them.
    pass


# Simple approach: for each cmd*.c in each tree, list all (subcmd, handler) pairs.
# Key on top-level 'prefix' derived from filename (cmdhfmf.c -> 'hf mf' etc.).

FAMILY_MAP_ICE = {
    'cmdhf14a.c':       'hf 14a',
    'cmdhf14b.c':       'hf 14b',
    'cmdhf15.c':        'hf 15',
    'cmdhfmf.c':        'hf mf',
    'cmdhfmfdes.c':     'hf mfdes',
    'cmdhfmfp.c':       'hf mfp',
    'cmdhfmfu.c':       'hf mfu',
    'cmdhficlass.c':    'hf iclass',
    'cmdhflegic.c':     'hf legic',
    'cmdhflist.c':      'hf list',
    'cmdhflto.c':       'hf lto',
    'cmdhffelica.c':    'hf felica',
    'cmdhffido.c':      'hf fido',
    'cmdhfntag424.c':   'hf ntag424',
    'cmdhfsaflok.c':    'hf saflok',
    'cmdhfseos.c':      'hf seos',
    'cmdhfst.c':        'hf st',
    'cmdhfst25ta.c':    'hf st25ta',
    'cmdhftesla.c':     'hf tesla',
    'cmdhftexkom.c':    'hf texkom',
    'cmdhfthinfilm.c':  'hf thinfilm',
    'cmdhftopaz.c':     'hf topaz',
    'cmdhfvas.c':       'hf vas',
    'cmdhfksx6924.c':   'hf ksx6924',
    'cmdhfepa.c':       'hf epa',
    'cmdhfgallagher.c': 'hf gallagher',
    'cmdhfgst.c':       'hf gst',
    'cmdhfict.c':       'hf ict',
    'cmdhfjooki.c':     'hf jooki',
    'cmdhfaliro.c':     'hf aliro',
    'cmdhfcipurse.c':   'hf cipurse',
    'cmdhfcryptorf.c':  'hf cryptorf',
    'cmdhfemrtd.c':     'hf emrtd',
    'cmdhffudan.c':     'hf fudan',
    'cmdhfsecc.c':      'hf secc',
    'cmdhfxerox.c':     'hf xerox',
    'cmdhfwaveshare.c': 'hf waveshare',

    'cmdlfawid.c':      'lf awid',
    'cmdlfcotag.c':     'lf cotag',
    'cmdlfdestron.c':   'lf destron',
    'cmdlfem.c':        'lf em',
    'cmdlfem410x.c':    'lf em 410x',
    'cmdlfem4x05.c':    'lf em 4x05',
    'cmdlfem4x50.c':    'lf em 4x50',
    'cmdlfem4x70.c':    'lf em 4x70',
    'cmdlffdxb.c':      'lf fdxb',
    'cmdlfgallagher.c': 'lf gallagher',
    'cmdlfguard.c':     'lf gproxii',
    'cmdlfhid.c':       'lf hid',
    'cmdlfhitag.c':     'lf hitag',
    'cmdlfhitaghts.c':  'lf hitag hts',
    'cmdlfhitagu.c':    'lf hitag u',
    'cmdlfidteck.c':    'lf idteck',
    'cmdlfindala.c':    'lf indala',
    'cmdlfio.c':        'lf io',
    'cmdlfjablotron.c': 'lf jablotron',
    'cmdlfkeri.c':      'lf keri',
    'cmdlfmotorola.c':  'lf motorola',
    'cmdlfnedap.c':     'lf nedap',
    'cmdlfnexwatch.c':  'lf nexwatch',
    'cmdlfnoralsy.c':   'lf noralsy',
    'cmdlfpac.c':       'lf pac',
    'cmdlfparadox.c':   'lf paradox',
    'cmdlfpcf7931.c':   'lf pcf7931',
    'cmdlfpresco.c':    'lf presco',
    'cmdlfpyramid.c':   'lf pyramid',
    'cmdlfsecurakey.c': 'lf securakey',
    'cmdlft55xx.c':     'lf t55xx',
    'cmdlfti.c':        'lf ti',
    'cmdlfviking.c':    'lf viking',
    'cmdlfvisa2000.c':  'lf visa2000',
    'cmdlfzx8211.c':    'lf zx8211',

    'cmdhw.c':          'hw',
    'cmddata.c':        'data',
    'cmdflashmem.c':    'mem',
    'cmdflashmemspiffs.c': 'mem spiffs',
    'cmdtrace.c':       'trace',
    'cmdusart.c':       'usart',
    'cmdsmartcard.c':   'smart',
    'cmdwiegand.c':     'wiegand',
    'cmdscript.c':      'script',
    'cmdnfc.c':         'nfc',
    'cmdanalyse.c':     'analyse',
    'cmdhf.c':          'hf',
    'cmdlf.c':          'lf',
}

# Legacy has different file set
FAMILY_MAP_LEG = dict(FAMILY_MAP_ICE)
# Legacy uses cmdlffdx.c instead of cmdlffdxb.c and names it "lf fdx"
FAMILY_MAP_LEG.pop('cmdlffdxb.c', None)
FAMILY_MAP_LEG['cmdlffdx.c']  = 'lf fdx'
# Legacy has cmdlfem4x.c (not split)
FAMILY_MAP_LEG['cmdlfem4x.c'] = 'lf em 4x'


# ---- build inventory ----

def inventory(tree_label, root, fam_map):
    """Return {full_cmd: {'file': path, 'line': N, 'handler': H}}"""
    inv = {}
    tabs = TABS[tree_label]
    for fn, prefix in fam_map.items():
        if fn not in tabs:
            continue
        for tbl_name, entries in tabs[fn]:
            for sub, handler, line in entries:
                if sub in ('help',):
                    continue
                # Skip separator-only entries (dashes only)
                if re.match(r'^-+$', sub):
                    continue
                full = f"{prefix} {sub}".strip()
                inv[full] = {
                    'file': fn,
                    'line': line,
                    'handler': handler,
                    'path': os.path.join(root, fn),
                }
    return inv


def extract_printandlog(path, handler, *, follow=True):
    """Extract PrintAndLogEx lines from a handler.
    If follow=True and the handler has no direct PrintAndLogEx but does call
    exactly one delegate in the same file, expand that delegate inline.
    """
    try:
        r = extract_handler(path, handler)
        if len(r) == 3:
            s, e, res = r
            delegates = set()
        else:
            s, e, res, delegates = r
    except Exception as ex:
        return None, None, [], set(), str(ex), None
    # If no direct prints and there's exactly one likely delegate in the same file,
    # recurse once to show its output.
    followed = None
    if follow and not res and len(delegates) == 1:
        only = next(iter(delegates))
        try:
            rr = extract_handler(path, only)
            if len(rr) == 3:
                s2, e2, res2 = rr; dels2 = set()
            else:
                s2, e2, res2, dels2 = rr
            if s2 is not None and res2:
                followed = (only, s2, res2)
        except Exception:
            pass
    return s, e, res, delegates, None, followed



# Severity -> prefix mapping (same in both trees)
SEVERITY_PREFIX = {
    'ERR':     '[!!]',
    'FAILED':  '[-]',
    'DEBUG':   '[#]',
    'HINT':    '[?]',
    'SUCCESS': '[+]',
    'WARNING': '[!]',
    'INFO':    '[=]',
    'NORMAL':  '',
    'INPLACE': '[-/|\\]',
}


def format_printandlog_row(line, level, body):
    # Extract format string arg (first quoted after level)
    # Body looks like PrintAndLogEx(LEVEL, "fmt" maybe, args...)
    # We extract from after the first ',' until end of string literal (may contain embedded macros)
    m = re.match(r'PrintAndLogEx\s*\(\s*[A-Z]+\s*,\s*(.*)\)\s*$', body.strip(), re.DOTALL)
    raw = m.group(1) if m else body
    # Just strip any trailing args we can't parse; keep the first " ... " literal group
    return (line, level, raw)


def render_handler_table(res):
    rows = []
    for line, level, body in res:
        rows.append(format_printandlog_row(line, level, body))
    return rows


def render(inv_ice, inv_leg, out_path):
    all_cmds = sorted(set(inv_ice) | set(inv_leg))
    summary = {
        'audited': len(all_cmds),
        'both': len([c for c in all_cmds if c in inv_ice and c in inv_leg]),
        'ice_only': len([c for c in all_cmds if c in inv_ice and c not in inv_leg]),
        'leg_only': len([c for c in all_cmds if c in inv_leg and c not in inv_ice]),
        'diverged': 0,
    }

    sections = []
    anomalies = []
    for full in all_cmds:
        ice = inv_ice.get(full)
        leg = inv_leg.get(full)
        # Extract
        ice_rows = []
        leg_rows = []
        ice_err = None
        leg_err = None
        ice_handler_line = None
        leg_handler_line = None
        ice_delegates = set()
        leg_delegates = set()
        ice_followed = None
        leg_followed = None
        if ice:
            _s, _e, res, dels, err, followed = extract_printandlog(ice['path'], ice['handler'])
            ice_handler_line = _s
            ice_delegates = dels
            ice_followed = followed
            if err:
                ice_err = err
            else:
                ice_rows = render_handler_table(res)
        if leg:
            _s, _e, res, dels, err, followed = extract_printandlog(leg['path'], leg['handler'])
            leg_handler_line = _s
            leg_delegates = dels
            leg_followed = followed
            if err:
                leg_err = err
            else:
                leg_rows = render_handler_table(res)

        # Build section
        lines = [f"## `{full}`"]
        if ice:
            lines.append("")
            lh = ice_handler_line if ice_handler_line else ice['line']
            lines.append(f"### Iceman (`{ice['file']}:{lh}` — `{ice['handler']}`, table @ line {ice['line']})")
            if ice_err:
                lines.append(f"> Extract error: {ice_err}")
            elif not ice_rows:
                lines.append("")
                lines.append("No user-facing PrintAndLogEx directly in handler body.")
                if ice_delegates:
                    lines.append(f"Delegates to: `{', '.join(sorted(ice_delegates))}`")
                if ice_followed:
                    fname, fline, fres = ice_followed
                    lines.append("")
                    lines.append(f"Expanded from delegate `{fname}` (`{ice['file']}:{fline}`):")
                    lines.append("")
                    lines.append("| Line | Level | Format string (with args) |")
                    lines.append("|---|---|---|")
                    for ln, level, body in fres:
                        # strip the outer PrintAndLogEx(LEVEL, ... ) so we just show the format string + args
                        mm = re.match(r'PrintAndLogEx\s*\(\s*[A-Z]+\s*,\s*(.*)\)\s*$', body.strip(), re.DOTALL)
                        raw = mm.group(1) if mm else body
                        raw_md = re.sub(r'\s+', ' ', raw).replace('|', '\\|')
                        if len(raw_md) > 350:
                            raw_md = raw_md[:350] + '...'
                        lines.append(f"| {ln} | {level} | `{raw_md}` |")
                    # expose the delegate as the 'rows' for divergence comparison
                    ice_rows = [(ln, lvl, body) for ln, lvl, body in fres]
                anomalies.append(f"{full}: iceman handler has no direct PrintAndLogEx (delegator to {', '.join(sorted(ice_delegates))})")
            else:
                lines.append("")
                lines.append("| Line | Level | Format string (with args) |")
                lines.append("|---|---|---|")
                for ln, level, raw in ice_rows:
                    raw_md = raw.replace('|', '\\|').replace('\n', ' ')
                    raw_md = re.sub(r'\s+', ' ', raw_md)
                    if len(raw_md) > 350:
                        raw_md = raw_md[:350] + '...'
                    lines.append(f"| {ln} | {level} | `{raw_md}` |")
                if ice_delegates:
                    lines.append("")
                    lines.append(f"Also calls helpers that may emit output: `{', '.join(sorted(ice_delegates))}`")
        else:
            lines.append("")
            lines.append("### Iceman")
            lines.append("")
            lines.append("**Command not present in iceman tree.**")

        if leg:
            lines.append("")
            lh = leg_handler_line if leg_handler_line else leg['line']
            lines.append(f"### Legacy fork (`{leg['file']}:{lh}` — `{leg['handler']}`, table @ line {leg['line']})")
            if leg_err:
                lines.append(f"> Extract error: {leg_err}")
            elif not leg_rows:
                lines.append("")
                lines.append("No user-facing PrintAndLogEx directly in handler body.")
                if leg_delegates:
                    lines.append(f"Delegates to: `{', '.join(sorted(leg_delegates))}`")
                if leg_followed:
                    fname, fline, fres = leg_followed
                    lines.append("")
                    lines.append(f"Expanded from delegate `{fname}` (`{leg['file']}:{fline}`):")
                    lines.append("")
                    lines.append("| Line | Level | Format string (with args) |")
                    lines.append("|---|---|---|")
                    for ln, level, body in fres:
                        # strip the outer PrintAndLogEx(LEVEL, ... ) so we just show the format string + args
                        mm = re.match(r'PrintAndLogEx\s*\(\s*[A-Z]+\s*,\s*(.*)\)\s*$', body.strip(), re.DOTALL)
                        raw = mm.group(1) if mm else body
                        raw_md = re.sub(r'\s+', ' ', raw).replace('|', '\\|')
                        if len(raw_md) > 350:
                            raw_md = raw_md[:350] + '...'
                        lines.append(f"| {ln} | {level} | `{raw_md}` |")
                    leg_rows = [(ln, lvl, body) for ln, lvl, body in fres]
                anomalies.append(f"{full}: legacy handler has no direct PrintAndLogEx (delegator to {', '.join(sorted(leg_delegates))})")
            else:
                lines.append("")
                lines.append("| Line | Level | Format string (with args) |")
                lines.append("|---|---|---|")
                for ln, level, raw in leg_rows:
                    raw_md = raw.replace('|', '\\|').replace('\n', ' ')
                    raw_md = re.sub(r'\s+', ' ', raw_md)
                    if len(raw_md) > 350:
                        raw_md = raw_md[:350] + '...'
                    lines.append(f"| {ln} | {level} | `{raw_md}` |")
                if leg_delegates:
                    lines.append("")
                    lines.append(f"Also calls helpers that may emit output: `{', '.join(sorted(leg_delegates))}`")
        else:
            lines.append("")
            lines.append("### Legacy fork")
            lines.append("")
            lines.append("**Command not present in legacy tree.**")

        # Divergence
        lines.append("")
        lines.append("### Divergence")
        if not ice:
            lines.append("")
            lines.append("Only in legacy tree.")
            summary['diverged'] += 1
        elif not leg:
            lines.append("")
            lines.append("Only in iceman tree.")
            summary['diverged'] += 1
        else:
            # Normalize format strings (strip PrintAndLogEx(LEVEL, ... ) wrapper if present)
            def _norm(body):
                mm = re.match(r'PrintAndLogEx\s*\(\s*[A-Z]+\s*,\s*(.*)\)\s*$', body.strip(), re.DOTALL)
                raw = mm.group(1) if mm else body
                return re.sub(r'\s+', ' ', raw).strip()
            ice_fmts = {_norm(r[2]) for r in ice_rows}
            leg_fmts = {_norm(r[2]) for r in leg_rows}
            if ice_fmts == leg_fmts:
                lines.append("")
                lines.append("No divergence (same format strings in same order).")
            else:
                # Compute added/removed
                only_ice = ice_fmts - leg_fmts
                only_leg = leg_fmts - ice_fmts
                lines.append("")
                if only_ice or only_leg:
                    lines.append(f"- Iceman-only lines: {len(only_ice)}")
                    lines.append(f"- Legacy-only lines: {len(only_leg)}")
                    # show a few samples
                    sample_ice = sorted(list(only_ice))[:3]
                    sample_leg = sorted(list(only_leg))[:3]
                    if sample_ice:
                        lines.append("")
                        lines.append("Sample iceman-only:")
                        for s in sample_ice:
                            s_short = s if len(s) < 200 else s[:200] + '...'
                            lines.append(f"  - `{s_short}`")
                    if sample_leg:
                        lines.append("")
                        lines.append("Sample legacy-only:")
                        for s in sample_leg:
                            s_short = s if len(s) < 200 else s[:200] + '...'
                            lines.append(f"  - `{s_short}`")
                    summary['diverged'] += 1
                else:
                    lines.append("No divergence (minor formatting).")
        lines.append("")
        lines.append("---")
        sections.append('\n'.join(lines))

    # Build index by family
    by_family = {}
    for cmd in all_cmds:
        fam = cmd.split(' ', 1)[0] if ' ' in cmd else cmd
        by_family.setdefault(fam, []).append(cmd)

    toc_lines = ["## Index by family", ""]
    for fam, cmds in sorted(by_family.items()):
        toc_lines.append(f"- **{fam}** ({len(cmds)} commands)")
    toc_lines.append("")

    header = [
        "# PM3 Source Strings — Legacy vs Iceman",
        "",
        f"_Generated by Extractor C on {date.today().isoformat()}_",
        "_Iceman tree: /tmp/rrg-pm3/client/src_",
        "_Legacy tree: /tmp/factory_pm3/client/src_",
        "",
        "## How this document was built",
        "",
        "1. Every `cmd*.c` in each tree is parsed to enumerate all `command_t` tables (both top-level `CommandTable` and nested sub-tables like `CommandNFCType1Table`).",
        "2. For each `(prefix, subcmd)` pair the corresponding handler function is located, the function body is isolated (brace-balance after comment/string masking), and every `PrintAndLogEx(LEVEL, ...)` call is captured with its source line number.",
        "3. If a handler has no direct `PrintAndLogEx` but calls exactly one plausible helper (matched by a name pattern like *print/show/dump/info/usage/demod/reader*), the helper in the same file is expanded inline and its prints are listed.",
        "4. Help/dispatcher entries and pure table-separator entries (dashes-only `sub`) are omitted from the per-command sections.",
        "",
        "`DEBUG` prints are filtered because they are gated by runtime state (`g_debugMode`). Help-text-only prints (e.g. `CLIParserInit` description arguments) are not emitted through `PrintAndLogEx` and therefore do not appear in the tables — they only reach the user on `-h`.",
        "",
        "Format strings are shown *verbatim* — color macros (`_GREEN_`/`_YELLOW_`/`_RED_`/`_CYAN_`/`_BLUE_`), the `NOLF` macro, and the `_CLEAR_`/`_TOP_` cursor-control macros are preserved so the refactor can match them byte-for-byte.",
        "",
        "## Summary",
        f"- Commands audited: {summary['audited']}",
        f"- Commands in both trees: {summary['both']}",
        f"- Commands only in iceman: {summary['ice_only']}",
        f"- Commands only in legacy: {summary['leg_only']}",
        f"- Commands with format-string divergence (incl. presence-only): {summary['diverged']}",
        "",
        "## Severity → stdout prefix mapping",
        "",
        "Identical in both trees (`ui.c`). When a `PrintAndLogEx(LEVEL, ...)` call reaches stdout, `LEVEL` maps to the prefix below:",
        "",
        "| Level | Prefix (no-emoji mode) |",
        "|---|---|",
        "| `ERR` | `[!!] ` (red, on stderr) |",
        "| `FAILED` | `[-] ` (red) |",
        "| `DEBUG` | `[#] ` (blue, suppressed unless `data setdebugmode`>0) |",
        "| `HINT` | `[?] ` (yellow, suppressed unless hints on) |",
        "| `SUCCESS` | `[+] ` (green) |",
        "| `WARNING` | `[!] ` (cyan) |",
        "| `INFO` | `[=] ` (yellow) |",
        "| `NORMAL` | (no prefix) |",
        "| `INPLACE` | `[\\]`/`[|]`/`[/]`/`[-]` spinner (yellow, no newline) |",
        "",
        "Iceman: `ui.c:295-348`. Legacy: `ui.c:195-241`. Both emit through `fPrintAndLog`.",
        "",
        "Color macros are defined in `ui.h` (iceman) / `ui.h` (legacy). When emoji mode is off they wrap to ANSI escapes; when the client is invoked without a TTY (e.g. `--stdin-run`) the macros resolve to empty strings and the prefix is just `[+] `, `[=] `, etc.",
        "",
    ] + toc_lines + [
        "---",
        "",
    ]

    body = '\n'.join(header) + '\n' + '\n'.join(sections)

    if anomalies:
        body += '\n\n## Anomalies / delegators\n\n'
        body += ("Handlers listed here have no direct `PrintAndLogEx` calls in their own body. "
                 "They either pass control entirely to a helper (in which case the single helper was expanded inline "
                 "in the per-command table above) or dispatch to a nested sub-table. Entries with `(delegator to )` had "
                 "no plausible helper name match — usually these are pure dispatchers calling `CmdsParse` on a nested "
                 "CommandTable (`nfc type1`, `nfc type2`, ...) and therefore produce no output themselves; follow into "
                 "the sub-table section for their subcommands.\n\n")
        for a in anomalies:
            body += f"- {a}\n"

    with open(out_path, 'w') as f:
        f.write(body)

    print(f"Wrote {out_path}")
    print(f"Commands audited: {summary['audited']}")
    print(f"Both: {summary['both']}, iceman-only: {summary['ice_only']}, legacy-only: {summary['leg_only']}")
    print(f"Diverged: {summary['diverged']}")
    print(f"Anomalies: {len(anomalies)}")


def main():
    inv_ice = inventory('iceman', ICEMAN_ROOT, FAMILY_MAP_ICE)
    inv_leg = inventory('legacy', LEGACY_ROOT, FAMILY_MAP_LEG)
    render(inv_ice, inv_leg, '/home/qx/icopy-x-reimpl/tools/ground_truth/source_strings.md')


if __name__ == '__main__':
    main()
