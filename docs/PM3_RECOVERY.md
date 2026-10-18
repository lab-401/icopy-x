# PM3 response ownership and recovery

A command may change a card before its reply is lost. Neither `executor` nor
`RemoteTaskManager` automatically replays it. `rework_max` remains accepted in
the executor API for existing callers; it no longer authorizes retries. An
explicit user retry or a protocol's own retry logic is a separate operation.

The executor uses an absolute response deadline, so a trickle of bytes cannot
extend a command indefinitely. `timeout <= 0` still permits an unlimited normal
wait. Cancellation or deadline expiry starts a **three-second drain** under the
existing operation lock. A late complete response is discarded; it cannot
populate the parser cache, save a successful read, or notify a cancelled UI.
The UI's nonblocking cancellation does not wait for this drain.

A complete response requires a terminal, newline-delimited `Nikola.D: N` or
`pm3 -->` line. EOF, process termination, reset notifications and partial text
are not completion. Factory and Iceman command translation is unchanged.

If draining fails, reconnecting alone is insufficient. Before sending another
PM3 command, the executor requests `Nikola.D.CTL = sync` on the new connection:

| Daemon reply | Meaning and executor action |
|---|---|
| `READY` | The command lock was acquired, the child is live, and no response is uncertain; new work may proceed. |
| `BUSY` | The previous owner did not release the lock within three seconds; fail the new operation without a reset or replay. A later user retry can check again. |
| `DIRTY` | The previous command lost its terminator, the child died, or cleanup invalidated it; attempt one explicit restart before new work. |
| Missing, partial or unknown reply | Fail closed and preserve the uncertainty flag. |

Control replies include their own completion marker. Restart returns `OK` only
after replacing the child and confirming that the replacement and its reader
remain live. Failed process creation, unreaped children and failed/timed-out
cleanup return `FAIL`. This acknowledges a fresh process, **not RF or USB
readiness**. The existing hardware settling delays remain; physical confirmation
is still required. Both updated modules must be deployed together in the IPK.

The daemon retains its 120-second command wait. Its event distinguishes real
completion from a wakeup caused by EOF or restart. Each reader belongs to one
process generation, so late output or exit from an old reader cannot complete
new work. A delayed Enter used to stop `hf tune`/`lf tune` also belongs to its
original command and cannot interrupt the next command.

## Evidence and limits

`tests/ui/test_pm3_transport_recovery.py` runs the actual executor, local TCP
server, daemon command ownership and stdout reader. Only the PM3 child process
is simulated. It covers delayed output, bounded failure while busy, incomplete
output/EOF, empty replies without replay, failed and successful restart,
generation isolation, failed cleanup, framing and trickled output. Event-based
synchronization and shortened deadlines keep the tests practical on host CI.

`critical-v5` adds two exact-package ARM/Tk cases to both package variants:
late LF output cannot create a successful read, and truncated LF output requires
an explicit READY acknowledgement before rescan. These use synthetic transport
faults and shortened LF/drain deadlines (30/400 ms), with a 150 ms late reply.
They run the actual packaged executor, Reader, parsers, dump handling and UI;
they do not execute the daemon or PM3 binary. Host tests cover the real daemon.

Physical follow-up requires a charged iCopy-XS and the EM410x tag: repeat normal
read, cancel/re-enter during LF search and during LF ID read, then verify a
fresh identity and UI responsiveness. Record wire timing, daemon ownership,
any restart and the saved file. Recheck Ultralight normal/empty-response retry
and PC-mode return. No badge writing or FPGA flashing is required for this
transport validation. ICS Decoder integration remains untested without the
accessory. These fixes do not explain the intermittent physical USCUID-UL
empty reply or guarantee success for every card family.
