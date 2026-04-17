# Phase 5 Consolidated Trace Sweep Report

Generator: `tests/phase5_sweep/test_full_trace_sweep.py`

## Regression gate: **PASS**

## Totals

| Firmware | Total | Pass | Fail | Stale | Noop | Unclass |
|----------|------:|-----:|-----:|------:|-----:|--------:|
| iceman | 258 | 239 | 0 | 19 | 103 | 0 |
| legacy | 3809 | 3809 | 0 | 0 | 344 | 0 |

## Top 10 commands by sample count

| Command | Total | Pass | Fail | Stale | Pass % |
|---------|------:|-----:|-----:|------:|-------:|
| `hf mf wrbl` | 2358 | 2358 | 0 | 0 | 100.0% |
| `hf 14a info` | 276 | 270 | 0 | 6 | 97.8% |
| `hf mf rdsc` | 218 | 218 | 0 | 0 | 100.0% |
| `hf mf cgetblk` | 150 | 150 | 0 | 0 | 100.0% |
| `lf sea` | 147 | 147 | 0 | 0 | 100.0% |
| `lf t55xx detect` | 128 | 128 | 0 | 0 | 100.0% |
| `lf t55xx read` | 78 | 78 | 0 | 0 | 100.0% |
| `hf sea` | 68 | 65 | 0 | 3 | 95.6% |
| `hf mf fchk` | 67 | 67 | 0 | 0 | 100.0% |
| `hf felica reader` | 47 | 47 | 0 | 0 | 100.0% |

## Full by-command breakdown

| Command | iceman (P/F/S) | legacy (P/F/S) |
|---------|---------------:|---------------:|
| `data save f` | 0/0/0 | 18/0/0 |
| `hf 14a config` | 3/0/0 | 0/0/0 |
| `hf 14a info` | 4/0/6 | 266/0/0 |
| `hf 14a list` | 3/0/0 | 4/0/0 |
| `hf 14a raw` | 10/0/0 | 29/0/0 |
| `hf 14a reader` | 1/0/0 | 3/0/0 |
| `hf 14a sim t` | 2/0/0 | 4/0/0 |
| `hf 14a sniff` | 2/0/0 | 5/0/0 |
| `hf 14b sniff` | 0/0/0 | 1/0/0 |
| `hf 15 csetuid` | 2/0/0 | 0/0/0 |
| `hf 15 dump` | 2/0/0 | 0/0/0 |
| `hf 15 dump f` | 3/0/0 | 0/0/0 |
| `hf 15 info` | 4/0/0 | 0/0/0 |
| `hf 15 restore` | 1/0/0 | 0/0/0 |
| `hf 15 restore f` | 2/0/0 | 0/0/0 |
| `hf felica litedump` | 0/0/0 | 1/0/0 |
| `hf felica reader` | 10/0/0 | 37/0/0 |
| `hf iclass chk` | 1/0/0 | 0/0/0 |
| `hf iclass dump` | 3/0/0 | 0/0/0 |
| `hf iclass dump k` | 2/0/0 | 1/0/0 |
| `hf iclass info` | 10/0/0 | 5/0/0 |
| `hf iclass rdbl` | 10/0/0 | 20/0/0 |
| `hf iclass sniff` | 0/0/0 | 1/0/0 |
| `hf iclass wrbl` | 0/0/10 | 0/0/0 |
| `hf list 14b` | 0/0/0 | 1/0/0 |
| `hf list iclass` | 0/0/0 | 1/0/0 |
| `hf list mf` | 2/0/0 | 5/0/0 |
| `hf mf cgetblk` | 10/0/0 | 140/0/0 |
| `hf mf cload` | 2/0/0 | 5/0/0 |
| `hf mf cwipe` | 1/0/0 | 3/0/0 |
| `hf mf darkside` | 6/0/0 | 1/0/0 |
| `hf mf fchk` | 10/0/0 | 57/0/0 |
| `hf mf nested` | 10/0/0 | 1/0/0 |
| `hf mf rdbl` | 0/0/0 | 1/0/0 |
| `hf mf rdsc` | 10/0/0 | 208/0/0 |
| `hf mf wrbl` | 10/0/0 | 2348/0/0 |
| `hf mfu dump` | 10/0/0 | 0/0/0 |
| `hf mfu dump f` | 5/0/0 | 5/0/0 |
| `hf mfu info` | 10/0/0 | 19/0/0 |
| `hf mfu restore` | 3/0/0 | 0/0/0 |
| `hf mfu restore s e f` | 1/0/0 | 5/0/0 |
| `hf sea` | 7/0/3 | 58/0/0 |
| `hf search` | 4/0/0 | 0/0/0 |
| `hf tune` | 1/0/0 | 4/0/0 |
| `hw ver` | 0/0/0 | 2/0/0 |
| `hw version` | 10/0/0 | 0/0/0 |
| `lf awid read` | 3/0/0 | 12/0/0 |
| `lf config` | 0/0/0 | 5/0/0 |
| `lf em 410x_read` | 0/0/0 | 2/0/0 |
| `lf em 410x_write` | 0/0/0 | 1/0/0 |
| `lf em 4x05 info` | 10/0/0 | 0/0/0 |
| `lf em 4x05_info` | 10/0/0 | 7/0/0 |
| `lf fdx clone c` | 0/0/0 | 6/0/0 |
| `lf fdx read` | 0/0/0 | 19/0/0 |
| `lf gallagher clone` | 0/0/0 | 4/0/0 |
| `lf gallagher read` | 0/0/0 | 14/0/0 |
| `lf hid clone` | 0/0/0 | 1/0/0 |
| `lf hid read` | 0/0/0 | 3/0/0 |
| `lf jablotron read` | 0/0/0 | 4/0/0 |
| `lf noralsy read` | 0/0/0 | 4/0/0 |
| `lf sea` | 10/0/0 | 137/0/0 |
| `lf t55xx chk f` | 0/0/0 | 12/0/0 |
| `lf t55xx detect` | 10/0/0 | 118/0/0 |
| `lf t55xx detect p` | 0/0/0 | 18/0/0 |
| `lf t55xx dump f` | 0/0/0 | 2/0/0 |
| `lf t55xx read` | 0/0/0 | 78/0/0 |
| `lf t55xx restore f` | 0/0/0 | 12/0/0 |
| `lf t55xx sniff` | 0/0/0 | 5/0/0 |
| `lf t55xx wipe` | 0/0/0 | 5/0/0 |
| `lf t55xx wipe p` | 1/0/0 | 39/0/0 |
| `lf t55xx write` | 4/0/0 | 31/0/0 |
| `lf tune` | 1/0/0 | 4/0/0 |
| `mem spiffs load f` | 1/0/0 | 4/0/0 |
| `mem spiffs wipe` | 1/0/0 | 3/0/0 |
| `script run hf_14a_raw` | 1/0/0 | 0/0/0 |

## Failures

_None._
