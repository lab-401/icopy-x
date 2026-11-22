# RNDIS network over the USB-C cable

The iCopy-X normally gets network only through the optional USB-C Ethernet
adapter, which cannot be used while charging. This feature multiplexes **power
and network on the same USB-C cable**: the device exposes a USB Ethernet
interface (RNDIS) to the host and runs a DHCP server, so `ssh root@10.1.1.1`
works with no manual configuration on either side.

```
device  usb0  10.1.1.1/24    (also the DHCP gateway)
host    DHCP  10.1.1.100-150, 12 h lease, gateway 10.1.1.1
```

Windows 10+ binds the interface natively as *Remote NDIS based Internet Sharing
Device*; Linux and macOS use `rndis_host`/`cdc_ether`. The device password is the
factory default `fa`.

## Design

### configfs gadget, not `g_ether`

The vendor kernel binds the legacy `g_ether` RNDIS function as CDC-ECM
(`class/subclass/protocol = 02/06/00`). Windows cannot drive that: it enumerates
as a serial port and then fails with `CM_PROB_FAILED_INSTALL` (problem 28).

A configfs gadget sets the RNDIS triple explicitly (`e0/01/03`) and adds a
Microsoft OS descriptor (`compatible_id=RNDIS`, `sub_compatible_id=5162001`), so
Windows loads the RNDIS driver on first plug-in. The gadget lives at
`/sys/kernel/config/usb_gadget/icopy` and is built by `tools/rndis/rndis.sh`.

### DHCP must be restarted with the gadget

`usb0` is created and destroyed together with the gadget. After a rebuild,
`dnsmasq --bind-interfaces` still points at the removed netdev: it keeps running
but silently stops answering, and the host falls back to an APIPA address
(`169.254.x.y`) — the link looks alive but routes nowhere.

`rndis.sh` therefore ends with `systemctl --no-block restart rndis-dhcp.service`.
`--no-block` avoids waiting on the `After=rndis.service` ordering while
`rndis.service` is still executing.

### Coexistence with PC mode and screen mirroring

The USB device controller hosts a single gadget driver at a time. While the
RNDIS gadget is bound, `g_acm_ms` (PC mode) or `g_serial` (screen mirroring) is
parked in

```
udc-core: couldn't find an available UDC - added [g_acm_ms] to list of pending drivers
```

and never enumerates: the host sees no COM port and no disk, and PC mode fails
silently.

`gadget_linux.release_rndis_udc()` detaches the configfs gadget before the app
loads its own, and `restore_rndis()` rebuilds it afterwards (which also re-binds
DHCP). Both are no-ops when the RNDIS gadget is not installed, so the same IPK
works on devices with and without this feature. Mirroring does the same around
`_load_gadget()` / `_unload_gadget()`.

configfs ignores a zero-length store, so the unbind writes a newline
(`echo "" > UDC`); writing `''` looks successful and does nothing.

## Installation

```bash
bash tools/rndis/install.sh              # root@10.1.1.1
bash tools/rndis/install.sh root@192.168.0.206
```

This installs `rndis.service`, `rndis-dhcp.service` and (for stock images)
`icopy-postpatch.service`. `tools/rndis/patch_stock_ipk.py` injects the
coexistence fix into an already installed app that predates this change; it
skips files that already contain `release_rndis_udc`, validates with `compile()`
before writing and never blocks boot.

An IPK built from this tree needs no patching.

## Verified on hardware

iCopy-X HW 1.7, OSS v1.1.7, kernel 4.14.111, Windows 10 19045:

| Step | Result |
|---|---|
| Boot | both services active, `usb0` carries `10.1.1.1/24` |
| Plug into PC | adapter gets `10.1.1.102` (`PrefixOrigin=Dhcp`), `ping 10.1.1.1` answers, SSH works |
| Enter PC mode | RNDIS released, host sees `COM9` and the mass-storage disk |
| Exit PC mode | gadget rebuilt, dnsmasq re-bound, host re-leases automatically, **no reboot** |
| Screen mirroring | releases/restores the same way |

`tools/rndis/verify_coexist.py` (shipped with the gadget-sharing change) asserts
the handover without root or hardware: the newline unbind, the
release-before-modprobe and restore-after-`g_serial` ordering, the mirror path,
and the no-op behaviour when no gadget is present.

To check what a **running device** actually executes, point the verifier at the
installed app — it reads the two modules statically and reports whether they use
the native helpers or the injected post-patch blocks:

```bash
python3 tools/rndis/verify_coexist.py --installed /home/pi/ipk_app_main/lib
```

Behavioural probing is deliberately not used there: the injected form writes the
live configfs path, so exercising it would detach the gadget carrying your SSH
session.

## Limits

- Power and network share one cable; the device still charges at the USB-C
  port's advertised current.
- The DHCP server answers on `usb0` only (`--bind-interfaces`), so it cannot
  leak leases onto the USB-C Ethernet adapter.
- `systemctl stop icopy` terminates X and blanks the panel. That is unrelated to
  this feature, but the installer's restart takes the UI down for ~20 s.
