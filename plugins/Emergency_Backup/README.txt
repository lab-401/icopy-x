iCopy-X / iCopy-XS - Emergency Backup
For devices with 16 GB microSD cards.
===================================

RESTORE A BACKUP TO A MICROSD CARD (WINDOWS)

IMPORTANT: FIRST RESTORE TEST
Always write the first backup image to a SPARE microSD card.
Keep the original, working card unchanged until the restored
card has been tested and the device boots correctly.
If the backup image is faulty, the original card will still
contain the working system.

USBImager (free): https://bztsrc.gitlab.io/usbimager/

1. On the iCopy device, finish Emergency Backup successfully.
2. Each backup is stored in its own folder, e.g.
   13.11.2026 19h12m. In PC Mode, copy the entire
   chosen folder to Windows, including all .001/.002 parts
   and Combine_Backup.bat / Combine_Backup.ps1.
3. Double-click Combine_Backup.bat and wait for SUCCESS.
   This joins and verifies the gzip image without extracting it.
   Keep every original numbered backup part safe.
4. Download and open USBImager on Windows.
5. Insert a SPARE microSD card of sufficient capacity.
   WARNING: writing the image ERASES ALL data on the selected card.
6. Select the combined icopyx-emergency-*.img.gz file.
7. Select the CORRECT microSD card, then click Write.
   Enable verification if your USBImager version offers it.
8. Safely eject the card when writing (and verification) finish.
9. Boot the restored card in the intended device.

IMPORTANT
- Do not select .001 or any other numbered part in USBImager.
- Do not unzip or extract the combined .img.gz file.
- If the join script reports an error, do not flash the image.
- The destination card must accommodate the original disk image;
  nominally identical-capacity cards may vary slightly in size.
- Restoring an Emergency Backup image to a card and booting iCopy-XS
  has been successfully tested on a 16 GB microSD setup.
  A newly written card should still be checked before relying on it.
