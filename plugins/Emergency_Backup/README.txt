iCopy-X / iCopy-XS - Emergency Backup
For devices with 16 GB microSD cards.
===================================

FEATURES
- Full compressed SD image: MBR/bootloader, P1 Boot, P2 RootFS,
  P3 Userdata, and reconstructed FAT32 P4 UDUMP.
- Backup parts are saved to a dated folder on UDUMP. Existing
  /backups files are excluded from the reconstructed UDUMP image.
- Checks the MBR, partition layout, UDUMP FAT32 and free space
  before creating an image. The original layout is preserved.
- Delete Backup: remove a selected complete backup folder.
- Clean Userdata: OPTIONAL cleanup of disposable files on the
  SOURCE microSD card, with scan, summary and confirmation.

CLEAN USERDATA (OPTIONAL)
1. Select Clean Userdata from the plugin's third menu option.
2. Review the counts/sizes found in the scan results.
3. Confirm cleaning, or cancel without changing the card.
4. After cleaning, return to the menu. You may reboot and check
   the device, then select Full SD Image for a new backup.

The cleanup targets are:
- Cached PIP files under /root/.cache/pip and /home/pi/.cache/pip.
- Selected APT cached .deb archives and pkgcache.bin / srcpkgcache.bin.
- Recognized log_*.txt files in /root/.proxmark3/logs and
  /home/pi/.proxmark3/logs.
- Existing Proxmark3 history.txt files are emptied to zero bytes;
  the filenames remain in place.

It does NOT clean /var/lib/apt/lists, installed programs, libraries,
Proxmark3 preferences, dictionaries or RFID dumps. Files that are
open or changed between scanning and cleaning are skipped when
identified. The reported space is a sum of file sizes and may not
match the reduction of the compressed raw disk image.

WARNING: Clean Userdata changes the LIVE SOURCE microSD card.
Deleted contents cannot be recovered without an earlier backup.
Keep a known-good full image before cleaning, even if the device
has successfully booted after cleaning on another test.

RESTORE A BACKUP TO A MICROSD CARD (WINDOWS)

IMPORTANT: FIRST RESTORE TEST
Always write the first backup image to a SPARE microSD card.
Keep the original working card unchanged until the restored card
has been tested and the device boots correctly.

USBImager (free): https://bztsrc.gitlab.io/usbimager/

1. Finish Emergency Backup successfully on the iCopy device.
2. In PC Mode, copy the ENTIRE dated backup folder to Windows,
   including all numbered .001/.002/... image parts and the
   Combine_Backup.bat / Combine_Backup.ps1 scripts.
3. Double-click Combine_Backup.bat; wait for SUCCESS. It joins
   and checks the gzip file without extracting it. Keep the
   original numbered parts safe.
4. Download and open USBImager on Windows.
5. Insert a SPARE microSD card of sufficient ACTUAL capacity.
   WARNING: writing an image ERASES ALL data on the selected card.
6. Select the combined icopyx-emergency-*.img.gz image, NOT one
   of the numbered image parts, in USBImager.
7. Check the destination carefully; click Write and enable
   verification if your USBImager version offers this feature.
8. Safely eject the card and boot it in the intended device.

IF USBIMAGER CANNOT ACCESS OR WRITE TO THE CARD
On some Windows systems, an SD card with existing Linux/EXT4
partitions may need its old partition layout removed first.
This is troubleshooting advice, NOT normally a requirement.
- Open Windows Disk Management (diskmgmt.msc).
- Identify the SPARE microSD card by capacity and disk number.
- If necessary, delete partitions on THAT CARD only, leaving
  its space Unallocated. Do not format or recreate partitions.
- Reopen USBImager and write the combined .img.gz file.
- If Windows Disk Management cannot delete the partitions,
  advanced users may use diskpart clean, but ONLY after verifying
  the correct disk number. This erases the chosen disk's layout.
NEVER clean or erase the original working iCopy-X/XS card.

IMPORTANT
- Do not select .001/.002/... parts directly in USBImager.
- Do not unzip or extract the combined .img.gz file.
- If the join script reports an error, DO NOT flash the image.
- Cards both sold as 16 GB may have different real capacities;
  the destination must fit the original source disk image.
- This plugin does not automatically adapt the image size to
  a smaller replacement card.

VERIFICATION
The backup/restore procedure was tested successfully on an
actual iCopy-XS with a 16 GB microSD card. In addition, after
Clean Userdata, the device booted successfully, a new full SD
backup was created and restored to another card, and the restored
iCopy-XS was reported to work normally, including its functions.
This confirms the test on that device, NOT every hardware revision.

Author: jareckib (2026)
