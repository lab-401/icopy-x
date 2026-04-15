# v1.0.90 Verified String Reference

Extracted from real `.so` modules under QEMU ARM on 2026-03-24.
Source of truth — NOT from transliterations.

## Titles (31)
| Key | Value |
|-----|-------|
| about | About |
| auto_copy | Auto Copy |
| backlight | Backlight |
| card_wallet | Dump Files |
| data_ready | Data ready! |
| diagnosis | Diagnosis |
| disk_full | Disk Full |
| key_enter | Key Enter |
| lua_script | LUA Script |
| main_page | Main Page |
| missing_keys | Missing keys |
| network | Network |
| no_valid_key | No valid key |
| no_valid_key_t55xx | No valid key |
| pc-mode | PC-Mode |
| read_tag | Read Tag |
| scan_tag | Scan Tag |
| se_decoder | SE Decoder |
| simulation | Simulation |
| snakegame | Greedy Snake |
| sniff_notag | Sniff TRF |
| sniff_tag | Sniff TRF |
| tag_info | Tag Info |
| time_sync | Time Settings |
| trace | Trace |
| update | Update |
| volume | Volume |
| warning | Warning |
| wipe_tag | Erase Tag |
| write_tag | Write Tag |
| write_wearable | Watch |

## Buttons (30)
| Key | Value |
|-----|-------|
| button | Button |
| cancel | Cancel |
| clear | Clear |
| delete | Delete |
| details | Details |
| edit | Edit |
| enter | Enter |
| fail | Fail |
| finish | Finish |
| force | Force |
| forceuse | Force-Use |
| no | No |
| pass | Pass |
| pc-m | PC-M |
| read | Read |
| reread | Reread |
| rescan | Rescan |
| retry | Retry |
| rewrite | Rewrite |
| save | Save |
| save_log | Save |
| shutdown | Shutdown |
| simulate | Simulate |
| sniff | Sniff |
| start | Start |
| stop | Stop |
| verify | Verify |
| wipe | Erase |
| write | Write |
| yes | Yes |

## Toast Messages (45)
| Key | Value |
|-----|-------|
| bcc_fix_failed | BCC repair failed |
| delete_confirm | Delete? |
| device_disconnected | USB device is removed! |
| err_at_wiping | Unknown error |
| game_over | Game Over |
| game_tips | Press 'OK' to start game. |
| keys_check_failed | Time out |
| no_tag_found | No tag found |
| no_tag_found2 | No tag found \nOr\n Wrong type found! |
| opera_unsupported | Invalid command |
| pausing | Pausing |
| pcmode_running | PC-mode Running... |
| plz_remove_device | Please remove USB device! |
| processing | Processing... |
| read_failed | Read Failed! |
| read_ok_1 | Read\nSuccessful!\nFile saved |
| read_ok_2 | Read\nSuccessful!\nPartial data\nsaved |
| sim_valid_input | Input invalid:\n{} greater than {} |
| sim_valid_param | Invalid parameter |
| simulating | Simulation in progress... |
| sniffing | Sniffing in progress... |
| start_clone_uid | Start writing UID |
| t5577_sniff_finished | T5577 Sniff Finished |
| tag_found | Tag Found |
| tag_multi | Multiple tags detected! |
| time_syncing | Synchronizing system time |
| time_syncok | Synchronization successful! |
| trace_loading | Trace\nLoading... |
| trace_saved | Trace file\nsaved |
| unknown_error | Unknown error. |
| update_finish | Update finish. |
| update_unavailable | No update available |
| verify_failed | Verification failed! |
| verify_success | Verification successful! |
| wipe_failed | Erase failed |
| wipe_no_valid_keys | No valid keys, Please use 'Auto Copy' first, Then erase |
| wipe_success | Erase successful |
| write_failed | Write failed! |
| write_success | Write successful! |
| write_verify_success | Write and Verify successful! |
| write_wearable_err1 | The original tag and tag(new)\n type is not the same. |
| write_wearable_err2 | Encrypted cards are not supported. |
| write_wearable_err3 | Change tag position on the antenna. |
| write_wearable_err4 | UID write failed. Make sure the tag is placed on the antenna. |
| you_win | You win |

## Item Messages (53)
| Key | Value |
|-----|-------|
| aboutline1 | `    {}` |
| aboutline1_update | Firmware update |
| aboutline2 | `   HW  {}` |
| aboutline2_update | 1.Download firmware |
| aboutline3 | `   HMI {}` |
| aboutline3_update | ` icopy-x.com/update` |
| aboutline4 | `   OS  {}` |
| aboutline4_update | 2.Plug USB, Copy firmware to device. |
| aboutline5 | `   PM  {}` |
| aboutline5_update | 3.Press 'OK' start update. |
| aboutline6 | `   SN  {}` |
| blline1-3 | Low, Middle, High |
| diagnosis_item1 | User diagnosis |
| diagnosis_item2 | Factory diagnosis |
| diagnosis_subitem1-9 | HF Voltage, LF Voltage, HF reader, LF reader, Flash Memory, USB port, Buttons, Screen, Sound |
| sniff_item1-5 | 1. 14A Sniff, 2. 14B Sniff, 3. iclass Sniff, 4. Topaz Sniff, 5. T5577 Sniff |
| valueline1-4 | Off, Low, Middle, High |
| wipe_m1 | Erase MF1/L1/L2/L3 |
| wipe_t55xx | Erase T5577 |

## Tag Types (48)
| ID | Constant | Display |
|----|----------|---------|
| -1 | UNSUPPORTED | |
| 0 | M1_S70_4K_4B | |
| 1 | M1_S50_1K_4B | |
| 2 | ULTRALIGHT | |
| 3 | ULTRALIGHT_C | |
| 4 | ULTRALIGHT_EV1 | |
| 5 | NTAG213_144B | |
| 6 | NTAG215_504B | |
| 7 | NTAG216_888B | |
| 8 | EM410X_ID | |
| 9 | HID_PROX_ID | |
| 10 | INDALA_ID | |
| 11 | AWID_ID | |
| 12 | IO_PROX_ID | |
| 13 | GPROX_II_ID | |
| 14 | SECURAKEY_ID | |
| 15 | VIKING_ID | |
| 16 | PYRAMID_ID | |
| 17 | ICLASS_LEGACY | |
| 18 | ICLASS_ELITE | |
| 19 | ISO15693_ICODE | |
| 20 | LEGIC_MIM256 | |
| 21 | FELICA | |
| 22 | ISO14443B | |
| 23 | T55X7_ID | |
| 24 | EM4305_ID | |
| 25 | M1_MINI | |
| 26 | M1_PLUS_2K | |
| 27 | TOPAZ | |
| 28 | FDXB_ID | |
| 29 | GALLAGHER_ID | |
| 30 | JABLOTRON_ID | |
| 31 | KERI_ID | |
| 32 | NEDAP_ID | |
| 33 | NORALSY_ID | |
| 34 | PAC_ID | |
| 35 | PARADOX_ID | |
| 36 | PRESCO_ID | |
| 37 | VISA2000_ID | |
| 38 | HITAG2_ID | |
| 39 | MIFARE_DESFIRE | |
| 40 | HF14A_OTHER | |
| 41 | M1_S70_4K_7B | |
| 42 | M1_S50_1K_7B | |
| 43 | M1_POSSIBLE_4B | |
| 44 | M1_POSSIBLE_7B | |
| 45 | NEXWATCH_ID | |
| 46 | ISO15693_ST_SA | |
| 47 | ICLASS_SE | |

## Menu Position Map (QEMU-verified)
| Pos | Activity | Verified Title |
|-----|----------|----------------|
| 0 | Auto Copy | "Auto Copy" |
| 1 | Dump Files | "Dump Files 1/6" |
| 2 | Scan Tag | "Scan Tag" |
| 3 | Read Tag | (crashes under QEMU) |
| 4 | Sniff TRF | "Sniff TRF 1/1" |
| 5 | Simulation | "Simulation 1/4" |
| 6 | PC-Mode | "PC-Mode" |
| 7 | Diagnosis | "Diagnosis" |
| 8 | Backlight | "Backlight" |
| 9 | Volume | "Volume" |
| 10 | About | "About 1/2" |
| 11 | Erase Tag | "Erase Tag" |
| 12 | Time Settings | "Time Settings" |
| 13 | LUA Script | "LUA Script 1/10" |

## QEMU-Verified Screen Content

### PC-Mode
- Prompt: "Please connect to\nthe computer.Then\npress start button"
- Buttons: Start / Start
- After M2: "Processing" toast, buttons change to Stop / Button

### Diagnosis
- Items: "User diagnosis", "Factory diagnosis"
- Sub-items (9): HF Voltage, LF Voltage, HF reader, LF reader, Flash Memory, USB port, Buttons, Screen, Sound

### Backlight
- Items: Low, Middle, High (3 items, NO "Off")
- CheckedListView with radio selection

### Volume
- Items: Off, Low, Middle, High (4 items)
- CheckedListView with radio selection

### Erase Tag
- Items: "1. Erase MF1/L1/L2/L3", "2. Erase T5577"

### Time Settings
- Display: boxed date YYYY — MM — DD / HH : MM : SS
- Buttons: Edit / Edit

### LUA Script
- List with pagination "1/10"
- Items from /mnt/upan/luascripts/: legic, test_t55x7_bi, mifareplus, mfu_magic, dumptoemul...

### Dump Files (6 pages)
Page 1: 1. Viking ID, 2. Ultralight & NTAG, 3. Visa2000 ID, 4. HID Prox ID, 5. Mifare Classic
Page 3: 11. NexWatch ID, 12. Securakey ID, 13. Felica, 14. KERI ID, 15. IO Prox ID
(Pages 2, 4, 5, 6 pending capture)

### Simulation (4 pages)
Page 1: 1. M1 S50 1k, 2. M1 S70 4k, 3. Ultralight, 4. Ntag215, 5. FM11RF005SH

### Sniff TRF (1 page)
Items: 1. 14A Sniff, 2. 14B Sniff, 3. iclass Sniff, 4. Topaz Sniff, 5. T5577 Sniff
