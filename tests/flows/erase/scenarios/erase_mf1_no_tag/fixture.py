# Erase MF1 — no tag present during scan
# Source: derived from .so binary analysis (erase.so no-tag path)
# hf 14a info returns ret=-1 with empty response (timeout, no card on reader)
SCENARIO_RESPONSES = {
    'hf 14a info': (-1, ''),
}
DEFAULT_RETURN = -1
