# LUA Script hf_read — PM3 connection failure (returns -1)
# Source: real device trace session 1 (20260330) — first attempt before PM3 reconnection
# PM3 command: script run hf_read (via startPM3Task, timeout=-1)
# PM3 returns -1 with empty response (connection error, device removed, etc.)
SCENARIO_RESPONSES = {
    'script run': (-1, ''),
}
DEFAULT_RETURN = -1
