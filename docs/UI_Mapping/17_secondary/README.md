# Secondary and Hidden Activities — Exhaustive UI Mapping

Sources:
- `activity_main.so` binary strings: `docs/v1090_strings/activity_main_strings.txt`
- `actmain.so` decompiled: `decompiled/actmain.c`
- `games.so` decompiled: `decompiled/games_ghidra_raw.txt`
- String table: `resources.py` StringEN (`tools/qemu_shims/resources.py`)

---

## 1. SnakeGameActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 21034: SnakeGameActivity.getManifest
line 21060: SnakeGameActivity.onKeyEvent
line 21109: SnakeGameActivity.onCreate
line 21172: SnakeGameActivity.__init__
```

Game engine class in `games.so` (games_ghidra_raw.txt lines 287-317):
```
GreedySnake.__init__      @0x0002123c  (line 312)
GreedySnake.init_route_map @0x0002120c (line 310)
GreedySnake.create_body    @0x00020fb4 (line 294)
GreedySnake.food           @0x000211b8 (line 308)
GreedySnake.eat            @0x00021044 (line 299)
GreedySnake.moving         @0x00021130 (line 305)
GreedySnake.direction      @0x00021104 (line 304)
GreedySnake.die            @0x00021288 (line 314)
GreedySnake.start          @0x0002130c (line 317)
GreedySnake.stop           @0x00021090 (line 300)
GreedySnake.pause          @0x0002101c (line 298)
GreedySnake.isrun          @0x00020eb0 (line 287)
GreedySnake.draw_thread    @0x000210bc (line 301)
GreedySnake.show_pre_toast @0x000212dc (line 315)
```

### State Machine

#### STATE: IDLE (Initial)
- **Title**: "Greedy Snake" (resources.py StringEN.title.snakegame, line 7)
- **Content**: Toast showing "Press 'OK' to start game."
  (resources.py StringEN.toastmsg.game_tips, line 8)
- **Navigation**:
  - OK: Start game, transition to PLAYING
  - PWR: Exit activity

#### STATE: PLAYING
- **Content**: Snake game grid rendered on framebuffer
  - Snake body drawn as blocks
  - Food item rendered
  - Score display
- **Navigation**:
  - UP/DOWN/M1/M2: Change snake direction (mapped to cardinal directions)
  - OK: Pause game, transition to PAUSED
  - PWR: Exit game

#### STATE: PAUSED
- **Content**: Toast showing "Pausing"
  (resources.py StringEN.toastmsg.pausing, line 8)
- **Navigation**:
  - OK: Resume game, transition to PLAYING
  - PWR: Exit game

#### STATE: GAME_OVER
- **Content**: Toast showing "Game Over"
  (resources.py StringEN.toastmsg.game_over, line 8)
- **Navigation**:
  - OK: Restart game
  - PWR: Exit activity

#### STATE: WIN
- **Content**: Toast showing "You win"
  (resources.py StringEN.toastmsg.you_win, line 8)
- **Navigation**:
  - OK: Restart game
  - PWR: Exit activity

---

## 2. WearableDeviceActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 20893: WearableDeviceActivity.write_uid_to_container
line 20894: WearableDeviceActivity.write_dat_to_wearable
line 20895: WearableDeviceActivity.setupBtnAtItemChange
line 20896: WearableDeviceActivity.on_wearable_write_call
line 20897: WearableDeviceActivity.onMultiPIUpdate
line 20898: WearableDeviceActivity.onKeyEvent
line 21026: WearableDeviceActivity.onData
line 21027: WearableDeviceActivity.__init__
```

### Purpose

Handles copying UID data to wearable devices (smartwatches with NFC).
Accessed via the "Watch" menu item.

### State Machine

#### STATE: STEP1_COPY_UID
- **Title**: "Watch" (resources.py StringEN.title.write_wearable, line 7)
- **Content**: Tips text showing:
  "1. Copy UID\n\nWrite UID to tag(new), please place new card on iCopy antenna, then click 'start'"
  (resources.py StringEN.itemmsg.write_wearable_tips1, line 11)
- **Footer buttons**:
  - M1: "Start" (resources.py StringEN.button.start, line 6)
- **Navigation**:
  - M1/OK: Begin UID write, transition to STEP2
  - PWR: Exit activity

#### STATE: STEP2_RECORD_UID
- **Content**: Tips text showing:
  "2. Record UID\n\nPlease use your watch to record the UID from the tag(new) and then click 'Finish'."
  (resources.py StringEN.itemmsg.write_wearable_tips2, line 11)
- **Footer buttons**:
  - M1: "Finish" (resources.py StringEN.button.finish, line 6)
- **Navigation**:
  - M1/OK: Transition to STEP3
  - PWR: Go back to STEP1

#### STATE: STEP3_WRITE_DATA
- **Content**: Tips text showing:
  "3. Write data\n\nplace your watch on iCopy antenna, then click 'start' to write data to your watch."
  (resources.py StringEN.itemmsg.write_wearable_tips3, line 11)
- **Footer buttons**:
  - M1: "Start" (resources.py StringEN.button.start, line 6)
- **Navigation**:
  - M1/OK: Begin wearable write via `write_dat_to_wearable()`
  - PWR: Go back to STEP2

### Error Toasts

- "The original tag and tag(new) type is not the same."
  (resources.py StringEN.toastmsg.write_wearable_err1, line 8)
- "Encrypted cards are not supported."
  (resources.py StringEN.toastmsg.write_wearable_err2, line 8)
- "Change tag position on the antenna."
  (resources.py StringEN.toastmsg.write_wearable_err3, line 8)
- "UID write failed. Make sure the tag is placed on the antenna."
  (resources.py StringEN.toastmsg.write_wearable_err4, line 8)

---

## 3. ReadFromHistoryActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 20951: ReadFromHistoryActivity.write_lf_dump
line 20952: ReadFromHistoryActivity.write_id
line 20953: ReadFromHistoryActivity.write_file_base
line 20954: ReadFromHistoryActivity.onKeyEvent
line 20955: ReadFromHistoryActivity.get_type
line 20956: ReadFromHistoryActivity.get_info
line 21006: ReadFromHistoryActivity.sim_for_info
line 21019: ReadFromHistoryActivity.onData
line 21020: ReadFromHistoryActivity.__init__
```

### Purpose

Handles loading and using previously saved dump files.
Accessed via "Dump Files" menu item (resources.py StringEN.title.card_wallet, line 7).

### State Machine

#### STATE: FILE_LIST
- **Title**: "Dump Files" (resources.py StringEN.title.card_wallet, line 7)
- **Content**: ListView showing saved dump files
  - Files with extensions: .bin, .eml, .txt
  - If no files: "No dump info. \nOnly support:\n.bin .eml .txt"
    (resources.py StringEN.tipsmsg.no_tag_history, line 9)
- **Navigation**:
  - UP/DOWN: Navigate file list
  - OK: Select file, show file details
  - PWR: Exit activity

#### STATE: FILE_DETAIL
- **Content**: File info display via `get_info()` and `get_type()`
- **Footer buttons**:
  - M1: "Write" or "Simulate" (depending on file type)
  - M2: "Delete" (resources.py StringEN.button.delete, line 6)
- **Navigation**:
  - M1: Write/simulate selected dump
  - M2: Delete file (shows "Delete?" confirmation toast,
    resources.py StringEN.toastmsg.delete_confirm, line 8)
  - PWR: Return to FILE_LIST

---

## 4. IClassSEActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 20966: IClassSEActivity.wait_exit_and_go_write
line 20967: IClassSEActivity.is_device_exists
line 21093: IClassSEActivity.onSEReader
line 21094: IClassSEActivity.onKeyEvent
line 21118: IClassSEActivity.wait_exit
line 21150: IClassSEActivity.onCreate
line 21200: IClassSEActivity.__init__
```

### Purpose

Handles iClass SE (Secure Element) tag reading via an external USB decoder device.
Accessed via "SE Decoder" menu item (resources.py StringEN.title.se_decoder, line 7).

### State Machine

#### STATE: WAITING_FOR_TAG
- **Title**: "SE Decoder" (resources.py StringEN.title.se_decoder, line 7)
- **Content**: Tips text showing:
  "\nPlease place\niClass SE tag on\nUSB decoder\n\nDo not place\nother types!"
  (resources.py StringEN.tipsmsg.iclass_se_read_tips, line 9)
- **Operation**: `is_device_exists()` polls for USB decoder presence
- **Navigation**:
  - PWR: Exit activity

#### STATE: READING
- **Content**: Progress display while SE decoder reads tag
- **Operation**: `onSEReader()` handles incoming data from USB decoder
- **Navigation**:
  - PWR: Cancel and exit

#### STATE: COMPLETE
- **Content**: Read data display
- **Operation**: `wait_exit_and_go_write()` prepares for write operation
- **Navigation**:
  - OK: Proceed to write
  - PWR: Exit

---

## 5. AutoExceptCatchActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 20889: AutoExceptCatchActivity.save_log
line 20989: AutoExceptCatchActivity.save_log.<locals>.run_save
line 20990: AutoExceptCatchActivity.onActExcept
```

Also in `decompiled/activity_main_ghidra_raw.txt` line 56817:
```
__pyx_pw_13activity_main_23AutoExceptCatchActivity_1onActExcept @0x0006a89c
```

### Purpose

Global exception handler activity. Automatically invoked when an unhandled exception
occurs in any activity. NOT user-accessible from menus.

### State Machine

#### STATE: ERROR_DISPLAY (Only state)
- **Title**: Not standard (exception handler)
- **Content**: Displays exception information
- **Footer buttons**:
  - M1: "Save" (resources.py StringEN.button.save_log, line 6) -- saves crash log
- **Operation**:
  - `onActExcept()`: Receives exception data from the activity stack
  - `save_log()`: Saves crash log to device storage via `run_save()` inner function
- **Navigation**:
  - M1: Save log file, then exit
  - PWR: Exit without saving

---

## 6. OTAActivity (actmain.so)

### Binary Evidence

Decompiled functions (actmain.c):
```
line 4574:  __pyx_pw_7actmain_11OTAActivity_11onCreate @0x0001b27c
line 7084:  __pyx_pw_7actmain_11OTAActivity_19onKeyEvent @0x0001dc64
line 7790:  __pyx_pw_7actmain_11OTAActivity_10onKeyEvent_1run_internal @0x0001e91c
line 8338:  __pyx_pw_7actmain_11OTAActivity_17startUpdate @0x0001f264
line 8688:  __pyx_pw_7actmain_11OTAActivity_15call @0x0001f81c
line 9638:  __pyx_pw_7actmain_11OTAActivity_13onDestroy @0x000209f4
line 9906:  __pyx_pw_7actmain_11OTAActivity_7dismissText @0x00020ed8
line 13516: __pyx_pw_7actmain_11OTAActivity_5showText @0x00024d2c
line 14777: __pyx_pw_7actmain_11OTAActivity_3onActivity @0x00026328
```

Additional methods (actmain.c string table):
```
line 199:   OTAActivity.onCreate
line 211:   OTAActivity.onKeyEvent
line 213:   OTAActivity.startUpdate
line 214:   OTAActivity.call
line 216:   OTAActivity.onDestroy
line 218:   OTAActivity.dismissText
line 229:   OTAActivity.showText
line 232:   OTAActivity.onActivity
line 235:   OTAActivity.__init__
line 242:   OTAActivity.startCheckBat
```

### Purpose

Handles firmware Over-The-Air updates. Launched from AboutActivity when an update file
is detected on the device storage.

### State Machine

#### STATE: BATTERY_CHECK
- **Title**: "Update" (resources.py StringEN.title.update, line 7)
- **Content**: Battery level check via `startCheckBat()`
  - If battery too low: Shows battery warning tips
    (resources.py StringEN.tipsmsg.ota_battery_tips1-5, line 9)
  - If battery sufficient: Shows update confirmation
- **Navigation**:
  - OK: Proceed to UPDATE_CONFIRM (if battery OK)
  - PWR: Cancel update

#### STATE: UPDATE_CONFIRM
- **Content**: Tips text showing:
  "Do you want to start the update?"
  (resources.py StringEN.tipsmsg.update_start_tips, line 9)
- **Footer buttons**:
  - M1: "Start" (resources.py StringEN.button.start, line 6)
- **Navigation**:
  - M1/OK: Begin update via `startUpdate()`
  - PWR: Cancel

#### STATE: UPDATING
- **Content**: Progress display via `showText()`
  - "During installation\ndo not turn off\n or power off, do not long press the button."
    (resources.py StringEN.tipsmsg.installation, line 9)
  - Progress bar: "Updating..." (resources.py StringEN.procbarmsg.updating, line 10)
  - With file info: "Updating with: " (resources.py StringEN.procbarmsg.updating_with, line 10)
- **Operation**: `startUpdate()` runs update process via `run_internal()` callback
- **Navigation**:
  - All keys blocked during update

#### STATE: UPDATE_COMPLETE
- **Content**: "The update is successful."
  (resources.py StringEN.tipsmsg.update_successful, line 9)
  OR "Install failed, code = {}" on failure
  (resources.py StringEN.tipsmsg.install_failed, line 9)
- **Navigation**:
  - Any key: Exit, device may reboot

---

## 7. SleepModeActivity (actmain.so)

### Binary Evidence

Decompiled functions (actmain.c):
```
line 4358:  __pyx_pw_7actmain_17SleepModeActivity_1onActivity @0x0001ae90
line 4440:  __pyx_pw_7actmain_17SleepModeActivity_8onCreate_lambda2 @0x0001b010
line 6852:  __pyx_pw_7actmain_17SleepModeActivity_5onKeyEvent @0x0001d874
line 11671: __pyx_pw_7actmain_17SleepModeActivity_10onKeyEvent_lambda3 @0x00022cd0
```

String table (actmain.c):
```
line 287:   SleepModeActivity.onKeyEvent
line 288:   SleepModeActivity.onActivity
line 291:   SleepModeActivity.onCreate
line 331:   SleepModeActivity
```

### Purpose

System sleep/screen-off activity. Activated by inactivity timeout.
NOT user-accessible from menus -- triggered automatically by the system.

### State Machine

#### STATE: SLEEPING (Only state)
- **Content**: Screen off / blank display
- **Operation**:
  - `onCreate()` with `lambda2` -- sets up sleep timer and display off
  - `onActivity()` -- receives wake-up events
- **Navigation**:
  - Any key press: Wake up device, `onKeyEvent()` with `lambda3` handles wake
  - PWR: Wake up and return to previous activity

---

## 8. WarningDiskFullActivity (actmain.so)

### Binary Evidence

Decompiled functions (actmain.c):
```
line 12145: __pyx_pw_7actmain_23WarningDiskFullActivity_1__init__ @0x000234bc
line 14170: __pyx_pw_7actmain_23WarningDiskFullActivity_3onCreate @0x000258f8
line 246:   __pyx_pw_7actmain_23WarningDiskFullActivity_7onKeyEvent
line 247:   __pyx_pw_7actmain_23WarningDiskFullActivity_5startClear
```

String table (actmain.c):
```
line 262:   WarningDiskFullActivity.startClear
line 263:   WarningDiskFullActivity.onKeyEvent
line 264:   WarningDiskFullActivity.onCreate
line 283:   WarningDiskFullActivity.__init__
line 298:   WarningDiskFullActivity
```

### Purpose

Warning dialog shown when device storage is full. Automatically triggered
by the system when disk space drops below threshold.

### State Machine

#### STATE: WARNING (Only state)
- **Title**: "Disk Full" (resources.py StringEN.title.disk_full, line 7)
- **Content**: Tips text showing:
  "The disk space is full.\nPlease clear it after backup."
  (resources.py StringEN.tipsmsg.disk_full_tips, line 9)
- **Footer buttons**:
  - M1: "Clear" (resources.py StringEN.button.clear, line 6)
- **Operation**: `startClear()` clears temporary/old files
  - Shows "Clearing..." progress (resources.py StringEN.procbarmsg.clearing, line 10)
- **Navigation**:
  - M1/OK: Begin clearing files via `startClear()`
  - PWR: Dismiss warning (risk: device may malfunction with full disk)

---

## 9. WarningT5X4X05KeyEnterActivity (activity_main.so)

### Binary Evidence

String table entries (activity_main_strings.txt):
```
line 20877: WarningT5X4X05KeyEnterActivity.onKeyEvent
line 20878: WarningT5X4X05KeyEnterActivity.onData
line 20900: WarningT5X4X05KeyEnterActivity.onCreate
line 20901: WarningT5X4X05KeyEnterActivity.__init__
```

Decompiled symbols:
```
__pyx_pw_13activity_main_30WarningT5X4X05KeyEnterActivity_5onData
__pyx_pw_13activity_main_30WarningT5X4X05KeyEnterActivity_7onKeyEvent
__pyx_pw_13activity_main_30WarningT5X4X05KeyEnterActivity_1__init__
```

### Purpose

Key entry dialog for T5577/EM4305 password-protected tags. Shown when a
T55xx tag is detected with an unknown password, allowing the user to
manually enter the known key.

### State Machine

#### STATE: KEY_ENTRY (Only state)
- **Title**: "Key Enter" (resources.py StringEN.title.key_enter, line 7)
  OR "No valid key" (resources.py StringEN.title.no_valid_key_t55xx, line 7)
- **Content**: Tips text showing:
  "Enter a known key for \nT5577 or EM4305"
  (resources.py StringEN.tipsmsg.enter_known_keys_55xx, line 9)
  With key input display:
  "Key:"
  (resources.py StringEN.tipsmsg.enter_55xx_key_tips, line 9)
- **Footer buttons**:
  - M1: "Enter" (resources.py StringEN.button.enter, line 6)
  - M2: "Cancel" (resources.py StringEN.button.cancel, line 6)
- **Navigation**:
  - UP/DOWN: Change digit value at cursor position
  - M1: Confirm key entry
  - M2: Cancel
  - PWR: Cancel, exit activity

---

## 10. Activity Accessibility Summary

| Activity | User-Accessible | Trigger |
|----------|----------------|---------|
| SnakeGameActivity | Yes (hidden menu) | Long-press or special combo from main menu |
| WearableDeviceActivity | Yes | "Watch" menu item |
| ReadFromHistoryActivity | Yes | "Dump Files" menu item |
| IClassSEActivity | Yes | "SE Decoder" menu item |
| AutoExceptCatchActivity | No | Automatic on unhandled exception |
| OTAActivity | Yes (indirect) | From AboutActivity when update file present |
| SleepModeActivity | No | Automatic on inactivity timeout |
| WarningDiskFullActivity | No | Automatic when disk space critical |
| WarningT5X4X05KeyEnterActivity | Yes (indirect) | During T55xx read/write when key needed |

---

## Key Bindings (All Secondary Activities)

### SleepModeActivity.onKeyEvent (actmain_ghidra_raw.txt line 6961)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| SLEEPING | wake + finish() | wake + finish() | wake + finish() | wake + finish() | wake + finish() | wake + finish() | wake + finish() | wake + finish() |

Any key wakes the device: restores previous backlight level and finishes (returns to previous activity).

### WarningDiskFullActivity.onKeyEvent (actmain_ghidra_raw.txt line 18785)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| WARNING | no-op | no-op | no-op | no-op | startClear() | finish() | startClear() | finish() |

M1/PWR = ignore warning and exit. M2/OK = clear dump files and exit.

### OTAActivity.onKeyEvent (actmain_ghidra_raw.txt line 7193)

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | startCheck() | finish() | startCheck() | finish() |

### UpdateActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| READY | no-op | no-op | no-op | no-op | startInstall() | no-op | startInstall() | finish() |
| INSTALLING | no-op | no-op | no-op | no-op | no-op | no-op | no-op | no-op |
| DONE | no-op | no-op | no-op | no-op | finish() | no-op | finish() | finish() |

### SnakeGameActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | start game | no-op | start game | finish() |
| PLAYING | direction | direction | direction | direction | no-op | no-op | no-op | pause -> IDLE |
| GAME_OVER | no-op | no-op | no-op | no-op | restart -> IDLE | no-op | restart -> IDLE | finish() |

### WearableDeviceActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| STEP_N | no-op | no-op | no-op | no-op | next step | finish() | next step | finish() |

3 steps (tips1, tips2, tips3). M2/OK advances to next step. After step 3: finish.

### SniffForMfReadActivity / SniffForT5XReadActivity / SniffForSpecificTag

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| IDLE | no-op | no-op | no-op | no-op | start sniff | finish() | start sniff | finish() |

### IClassSEActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| INFO | no-op | no-op | no-op | no-op | no-op | finish() | no-op | finish() |

Read-only info display. M1/PWR exit.

### AutoExceptCatchActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| ERROR | no-op | no-op | no-op | no-op | finish() | no-op | finish() | finish() |

### WarningT5XActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| WARNING | no-op | no-op | no-op | no-op | proceed + finish() | finish() | proceed + finish() | finish() |

### WarningT5X4X05KeyEnterActivity.onKeyEvent

| State | UP | DOWN | LEFT | RIGHT | OK | M1 | M2 | PWR |
|-------|-----|------|------|-------|-----|-----|-----|------|
| KEY_ENTRY | rollUp() | rollDown() | prevChar() | nextChar() | confirm + finish() | finish() | confirm + finish() | finish() |

8-digit hex key entry. UP/DOWN roll hex digits (0-F). LEFT/RIGHT move cursor. M2/OK confirm and return key. M1/PWR cancel.

**Source:** `src/lib/activity_main.py` lines 5025-5404, `src/lib/actmain.py`, `decompiled/actmain_ghidra_raw.txt`.
