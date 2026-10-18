# Ultralight read acceptance

A completed Proxmark command is not evidence of a complete saved read.
`hfmfuread.read` checks the newly generated binary before caching its path:
regular file, bounded length, header/page consistency and the scanned seven-byte
UID. Missing, empty, raw-page-only, truncated, oversized and wrong-card files
fail. Existing binary/JSON names are skipped; exhausted names fail before a
command runs. Invalid output is retained for diagnosis but not offered as the
current read's write bundle.

Both shipped client families produce the 56-byte `mfu_dump_t` header, followed
by four bytes per page. Byte 11 is the maximum stored page index, so the exact
length is `56 + 4 * (byte[11] + 1)`. This validates new reader output; it does
not change historical dump import/conversion in Dump Files.

- [Factory-derived header](https://github.com/iCopy-X-Community/icopyx-community-pm3/blob/15dbe1bb49c06d161c6136b6a7125a36b1a40f62/include/mifare.h)
  and [dump writer](https://github.com/iCopy-X-Community/icopyx-community-pm3/blob/15dbe1bb49c06d161c6136b6a7125a36b1a40f62/client/src/cmdhfmfu.c):
  `dump_file_data.pages = pages - 1`, length `pages * 4 + 56`.
- [Iceman v4.23346 header](https://github.com/RfidResearchGroup/proxmark3/blob/dc0110c29d320e04b37ea436ee2924901407ae72/include/mifare.h)
  and [dump writer](https://github.com/RfidResearchGroup/proxmark3/blob/dc0110c29d320e04b37ea436ee2924901407ae72/client/src/cmdhfmfu.c)
  use the same fields and size.

The factory console printer subtracts one again when showing `Max data page`;
historical traces therefore print 14/60 bytes for a 16-page/64-byte payload.
Do not validate the binary against that erroneous display summary.

Full capacities for the supported menu types are Ultralight 16 pages,
Ultralight C 48, EV1 20 or 41, and NTAG213/215/216 45/135/231. EV1's version
storage byte distinguishes its sizes when available. Structurally valid shorter
data, or an explicit partial-dump response, is retained as **partial**. A
44-page Ultralight C read without its key pages is consequently partial.
Unknown EV1 version bytes retain both supported capacities for compatible cards;
this is not cryptographic proof of the card model or readable secret keys.

The Reader delivers an explicit `partial` completion flag while keeping the
existing path-shaped write bundle. Read and Auto Copy display their existing
“Partial data saved” state. Forced Classic reads retain their separate `force`
flag. Cancellation still suppresses callbacks and does not roll back saved files.

Host tests exercise the real reader/file boundary and both activities. The
critical-v4 QEMU profile runs packaged ARM code for full/partial reads, missing,
empty and truncated files, an empty response, and Auto Copy's partial result.
PM3 responses and client-produced files are explicitly simulated. Iceman text
is informed by the 2026-10-18 physical USCUID-UL session; UID/payload and all
factory responses are synthetic. QEMU does not execute PM3 or establish RF.

That physical session also observed one silent dump failure followed by a
successful read. The application correctly failed the empty response. Its RF,
card or client/firmware cause remains unresolved; this validation change does
not claim to repair it or introduce automatic command retries.
