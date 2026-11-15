# RNDIS USB network (power + network over one USB-C cable)

Gives the iCopy-X a network link to the PC **while charging**, with no manual IP
configuration on either side: the device runs a DHCP server, the PC gets a lease.

```
device  usb0  10.1.1.1/24   (DHCP gateway)
PC      DHCP   10.1.1.100-150, 12 h lease, gateway 10.1.1.1
```

Host side: Windows 10+ binds it natively as *Remote NDIS based Internet Sharing
Device*; Linux/macOS use `cdc_ether`/`rndis_host`. Then `ssh root@10.1.1.1`
(password `fa`).

## Files

| File | Role |
|---|---|
| `rndis.sh` | Builds the configfs gadget, puts the addresses on `usb0`, restarts the DHCP service. Idempotent — safe to re-run. |
| `rndis.service` | Runs `rndis.sh` at boot (`RemainAfterExit=yes`). |
| `rndis-dhcp.service` | `dnsmasq` in DHCP-only mode on `usb0`. |
| `patch_stock_ipk.py` | Injects the coexistence fix into an installed *stock* app (see below). |
| `icopy-postpatch.service` | Runs the patcher at boot, before `icopy.service`. |
| `install.sh` | Deploys all of the above over SSH. |

## Why configfs and not `g_ether`

The vendor kernel binds legacy RNDIS as CDC-ECM (`class/subclass/protocol =
02/06/00`), which Windows cannot drive — it enumerates as a serial port and then
fails with `CM_PROB_FAILED_INSTALL` (problem 28). A configfs gadget lets us set
the RNDIS triple explicitly (`e0/01/03`) plus a Microsoft OS descriptor
(`compatible_id=RNDIS`, `sub_compatible_id=5162001`), so Windows loads the RNDIS
driver on first plug-in.

## Why the DHCP service has to be restarted

`usb0` is created and destroyed together with the gadget. After a rebuild
`dnsmasq` (`--bind-interfaces`) still points at the removed netdev, silently
stops answering, and the PC falls back to an APIPA address (`169.254.x.y`) — the
link looks alive but nothing routes. `rndis.sh` therefore ends with
`systemctl --no-block restart rndis-dhcp.service`; `--no-block` avoids waiting on
the `After=rndis.service` ordering while `rndis.service` is still executing.

## Coexistence with PC mode and screen mirroring

The UDC hosts **one** gadget driver at a time. While this gadget is bound,
`g_acm_ms` (PC mode) or `g_serial` (mirroring) is parked in
`udc-core: couldn't find an available UDC - added [...] to list of pending
drivers` and never enumerates — PC mode fails silently, with no COM port and no
disk on the PC.

The fix lives in the app (`src/middleware/gadget_linux.py`,
`src/lib/mirror_service.py`) and ships as a separate change; `patch_stock_ipk.py`
below injects the same logic into an already installed app:

* `release_rndis_udc()` detaches the configfs gadget before the app loads its own
  gadget. configfs ignores a zero-length store, so the unbind writes a **newline**
  (`echo "" > UDC`), not `''`; writing zero bytes is a silent no-op.
* `restore_rndis()` restarts `rndis.service` afterwards, which rebuilds the gadget
  and re-binds DHCP.

Both are no-ops when the RNDIS gadget is not installed, so the IPK stays portable.

**Stock/factory images cannot be rebuilt**, which is what `patch_stock_ipk.py` is
for: it inserts the same logic into
`/home/pi/ipk_app_main/lib/{gadget_linux,mirror_service}.py`, skips files that
already contain `release_rndis_udc`, validates syntax with `compile()` before
writing, keeps `*.prepostpatch` backups and never blocks boot.

## Verified on hardware (HW 1.7, OSS v1.1.7, kernel 4.14.111)

| Step | Result |
|---|---|
| Boot | `rndis.service` + `rndis-dhcp.service` active, `usb0` carries `10.1.1.1/24` |
| PC | Windows adapter gets `10.1.1.102` (`PrefixOrigin=Dhcp`), `ping 10.1.1.1` |
| Enter PC mode | RNDIS released → `COM9` + `G:` mass storage appear (25.79 GB) |
| Exit PC mode | gadget rebuilt, dnsmasq re-bound, PC re-leases automatically — **no reboot** |

## Caveat

`systemctl stop icopy` SIGTERMs `xinit`; the framebuffer stops updating and the
screen goes blank. Never restart the app while somebody is mid-copy.
