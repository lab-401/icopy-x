#!/bin/sh
# Pure RNDIS gadget for iCopy-X: USB-C to PC gives power + network.
# Windows 10+ binds it natively (compatible id RNDIS/5162001).
#
# Device side: 10.1.1.1/24 (DHCP gateway)
# Re-run at any time; safe when already configured.
G=/sys/kernel/config/usb_gadget/icopy
F=$G/functions/rndis.usb0

mountpoint -q /sys/kernel/config || mount -t configfs none /sys/kernel/config

if [ -d "$G" ]; then
    echo "" > "$G/UDC" 2>/dev/null || true
    rm -f "$G/configs/c.1/rndis.usb0" "$G/os_desc/c.1" 2>/dev/null || true
    rmdir "$F/os_desc/interface.rndis" "$F/os_desc" "$F" 2>/dev/null || true
    rmdir "$G/configs/c.1/strings/0x409" "$G/configs/c.1" 2>/dev/null || true
    rmdir "$G/strings/0x409" "$G/os_desc" 2>/dev/null || true
    rmdir "$G" 2>/dev/null || true
fi

for m in g_ether g_serial g_acm_ms g_mass_storage; do
    modprobe -r "$m" 2>/dev/null || true
done

mkdir -p "$G"
echo 0x1d6b > "$G/idVendor"
echo 0x0104 > "$G/idProduct"
echo 0x0100 > "$G/bcdDevice"
echo 0x0201 > "$G/bcdUSB"
mkdir -p "$G/strings/0x409"
echo "icopyx-0001" > "$G/strings/0x409/serialnumber"
echo "Lab401" > "$G/strings/0x409/manufacturer"
echo "iCopy-X RNDIS" > "$G/strings/0x409/product"

mkdir -p "$F"
# This vendor kernel defaults these to CDC-ECM (02/06/00) which Windows
# cannot drive; RNDIS needs e0/01/03.
echo e0 > "$F/class"
echo 01 > "$F/subclass"
echo 03 > "$F/protocol"
echo "02:11:22:33:44:55" > "$F/dev_addr"
echo "02:11:22:33:44:66" > "$F/host_addr"

mkdir -p "$F/os_desc/interface.rndis"
echo "RNDIS" > "$F/os_desc/interface.rndis/compatible_id" 2>/dev/null || true
echo "5162001" > "$F/os_desc/interface.rndis/sub_compatible_id" 2>/dev/null || true
echo 1 > "$G/os_desc/use" 2>/dev/null || true

mkdir -p "$G/configs/c.1/strings/0x409"
echo "RNDIS" > "$G/configs/c.1/strings/0x409/configuration"
ln -s "$F" "$G/configs/c.1/" 2>/dev/null || true
ln -s "$G/configs/c.1" "$G/os_desc/c.1" 2>/dev/null || true

echo musb-hdrc.4.auto > "$G/UDC" || echo "UDC bind failed"

# The netdev is created asynchronously once the function exists.
i=0
while [ $i -lt 25 ] && [ ! -e /sys/class/net/usb0 ]; do
    sleep 0.2
    i=$((i + 1))
done

if [ -e /sys/class/net/usb0 ]; then
    nmcli device set usb0 managed no 2>/dev/null || true
    ip link set usb0 up
    ip addr add 10.1.1.1/24 dev usb0 2>/dev/null || true
fi

# usb0 may have been recreated: make sure dnsmasq is bound to the new one.
systemctl --no-block restart rndis-dhcp.service >/dev/null 2>&1 || true

echo "RNDIS gadget up: $(ip -4 addr show usb0 2>/dev/null | awk '/inet /{printf "%s ", $2}') / udc=$(cat /sys/class/udc/musb-hdrc.4.auto/state 2>/dev/null)"
