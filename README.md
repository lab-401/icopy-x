Just to be clear… my modifications to the software are based on the Lab401 source — they are the authors of this device, the ones who made it possible for us to update it, change the graphics, and so on.
Recently, on various forums, I’ve been hit with criticism claiming that I present myself as the author of this software. One messed‑up idiot decided to latch onto me. A complete nutcase. He contributed absolutely nothing to make iCopy‑X a better tool.

But… whatever, I’m over it now.
Here on GitHub there will only be a ZIP package containing everything that’s needed.

Unfortunately, my modifications require firmware changes — meaning the fullimage.elf.
In the ZIP package I’ll also include a 1:1 microSD image made with Macrium Reflect 8.0.7783 — the last free version — for people who accidentally trigger a boot timeout. Although from experience, I know you can simply remove the card and overwrite the files in the directory:
mmcblk03 → root/home/pi/ipk_app_main.

I also added — maybe unnecessarily — but in the main menu, in the Scan Tag option, Hitag2/Paxton detection is now included, and auto‑copy works in the menu as well as the S/R/W button. Only blocks 4, 5, 6, 7 are written — so there is no risk of bricking a blank tag, because block 3 (where the password is) is not written.

And to that idiot who criticized me without contributing any meaningful code changes — good luck.
And once again — I have never, anywhere, claimed to be the author of something I’m not.
If that screwed‑up head has a problem, he can take me to court, because honestly I’m starting to wonder if it’s even worth contributing for free for such clowns.
