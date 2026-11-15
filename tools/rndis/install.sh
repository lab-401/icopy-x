#!/bin/bash
# Deploy the always-on USB network (RNDIS + DHCP) to an iCopy-X over SSH.
#
#   bash tools/rndis/install.sh                 # root@10.1.1.1 (USB-C / RNDIS)
#   bash tools/rndis/install.sh root@192.168.0.206
#
# The device password is "fa" (factory default). Uses sshpass when available,
# otherwise plain ssh (you will be prompted).
set -e

HOST="${1:-root@10.1.1.1}"
DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v sshpass >/dev/null 2>&1; then
    SSH="sshpass -p fa ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no"
    SCP="sshpass -p fa scp -o StrictHostKeyChecking=no"
else
    SSH="ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no"
    SCP="scp -o StrictHostKeyChecking=no"
fi

echo "=== target: $HOST"
$SSH "$HOST" 'uname -a; cat /sys/class/udc/*/../uevent 2>/dev/null | head -1'

echo "=== copying files"
$SCP "$DIR/rndis.sh" "$HOST:/home/pi/rndis.sh"
$SCP "$DIR/rndis.service" "$DIR/rndis-dhcp.service" "$DIR/icopy-postpatch.service" \
     "$HOST:/etc/systemd/system/"
$SCP "$DIR/patch_stock_ipk.py" "$HOST:/usr/local/sbin/icopy_postpatch.py"

echo "=== enabling services"
$SSH "$HOST" '
  chmod +x /home/pi/rndis.sh /usr/local/sbin/icopy_postpatch.py
  systemctl daemon-reload
  systemctl enable rndis.service rndis-dhcp.service icopy-postpatch.service
  systemctl restart rndis.service
  systemctl restart rndis-dhcp.service
  systemctl start icopy-postpatch.service
'

echo "=== done. Verify from the host:"
echo "    ping 10.1.1.1 && ssh $HOST 'ip -4 addr show usb0'"
echo
echo "NOTE: the patch takes effect on the next app start.  Restarting"
echo "      'icopy.service' kills X (the screen goes blank for ~20 s) — do it"
echo "      only when nobody is using the device."
