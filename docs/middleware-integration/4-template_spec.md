# template.so Specification

**Module**: `template.so` (Cython, compiled ARM v7 LE)  
**Source**: `template.c` (Cython 0.29.21), originally `template.py`  
**Ground truth**: Ghidra decompilation of `orig_so/lib/template.so` (MD5: `1b92d5017a72e8defb8c88396e1bbb19`)  
**Imports**: `font`, `re`, `resources`, `tagtypes`  

## Purpose

`template.so` is the scan/read result display renderer. After `scan.so` identifies a tag,
`template.draw()` renders the tag info card to the tkinter canvas -- showing the tag family
name, frequency, UID, SAK, ATQA, and other type-specific fields. It is the **only** module
responsible for rendering found-tag information on screen.

---

## 1. Exported Functions

### `draw(typ, data, parent)`

**Signature** (from module audit + decompiled `__pyx_pw_8template_29draw`):  
```python
def draw(typ: int, data: dict, parent: Canvas) -> None
```

**Parameters**:
- `typ` -- integer tag type ID (0-47, from `tagtypes` module)
- `data` -- dict containing scan result data (keys depend on tag type)
- `parent` -- tkinter Canvas to draw on

**Behavior** (from decompiled code at `0x0001e1d0`):
1. Looks up `typ` in `TYPE_TEMPLATE` dict
2. If `typ` not in `TYPE_TEMPLATE`: calls `print()` with an error message and returns `None`
3. If found: extracts `draw_func` (index 3 of the tuple) and checks if it is `None`
4. If `draw_func` is `None`: same `print()` + return `None` path
5. If `draw_func` exists and `data` is `None`: calls `draw_func(data, parent)` -- just renders the template header (frequency, family name)
6. If `draw_func` exists and `data` is not `None`: calls `draw_func(data, parent)` with full data rendering

**From decompiled logic** (lines 4286-4584):
- First checks `typ in TYPE_TEMPLATE` via `PySequence_Contains`
- If not contained: returns `None` (no error, silent)
- If contained: retrieves `TYPE_TEMPLATE[typ]`, gets item at index `[3]` (the draw function)
- If draw_func is `None` (the sentinel value): returns `None`
- If draw_func exists: calls `draw_func(data, parent)` as a 2-arg call

### `dedraw(parent)`

**Signature** (from module audit + decompiled `__pyx_pw_8template_31dedraw`):  
```python
def dedraw(parent: Canvas) -> None
```

**Parameters**:
- `parent` -- tkinter Canvas to clear

**Behavior** (from decompiled code at `0x0001d710`):
1. Calls `parent.delete()` three times with different tag strings to remove template-drawn items
2. The three delete calls correspond to removing:
   - The title/family text area
   - The frequency line
   - The data lines (UID, SAK, ATQA, etc.)

**From decompiled structure** (lines 3561-4151):
The function performs a sequence of `parent.delete(tag)` calls. It:
1. Gets `parent.delete` method reference
2. Calls `str(x, y)` to create coordinate-based tags
3. Deletes items tagged with these coordinates
This clears all canvas items previously created by the draw functions.

### `create_by_parent(parent, tag)`

**Signature** (from module audit + decompiled `__pyx_pw_8template_1create_by_parent`):  
```python
def create_by_parent(parent: Canvas, tag: int) -> str
```

**Parameters**:
- `parent` -- tkinter Canvas (or widget that provides the canvas)
- `tag` -- integer tag type ID

**Behavior** (from decompiled code at `0x0001d248`):
1. Calls `str(tag)` to convert the tag type to a string
2. Looks up the tag type using the `tagtypes` module (via `__Pyx_PyObject_CallOneArg`)
3. Concatenates the result with a suffix string
4. Returns the concatenated string via `PyNumber_Add`

This function creates a display-name string for a given tag type, used by the parent
activity to label scan result cards.

---

## 2. TYPE_TEMPLATE Structure

The central data structure is a module-level dict mapping integer tag type IDs to 4-tuples.

**Type**: `Dict[int, Tuple[str, Optional[str], str, Callable]]`

**Format**: `{type_id: (frequency, display_name, family, draw_func)}`

Where:
- `frequency` -- `'13.56MHZ'` or `'125KHZ'`
- `display_name` -- human-readable tag name (e.g. `'M1 S50 1K (4B)'`), or `None` for writable-only tags
- `family` -- tag family string (e.g. `'MIFARE'`, `'NFCTAG'`, `'EM Marin'`)
- `draw_func` -- reference to the internal `__drawXxx` function for this tag type

### Complete TYPE_TEMPLATE (48 entries)

Source: QEMU extraction (module audit), cross-referenced with decompiled strings and template_strings.txt.

| ID | Frequency  | Display Name       | Family      | Draw Func         |
|----|-----------|--------------------|--------------|--------------------|
| 0  | 13.56MHZ  | M1 S70 4K (4B)    | MIFARE       | __drawM1           |
| 1  | 13.56MHZ  | M1 S50 1K (4B)    | MIFARE       | __drawM1           |
| 2  | 13.56MHZ  | Ultralight         | MIFARE       | __drawMFU          |
| 3  | 13.56MHZ  | Ultralight C       | MIFARE       | __drawMFU          |
| 4  | 13.56MHZ  | Ultralight EV1     | MIFARE       | __drawMFU          |
| 5  | 13.56MHZ  | NTAG213 144b       | NFCTAG       | __drawMFU          |
| 6  | 13.56MHZ  | NTAG215 504b       | NFCTAG       | __drawMFU          |
| 7  | 13.56MHZ  | NTAG216 888b       | NFCTAG       | __drawMFU          |
| 8  | 125KHZ    | EM410x ID          | EM Marin     | __drawID           |
| 9  | 125KHZ    | HID Prox ID        | HID Prox     | __drawID           |
| 10 | 125KHZ    | Indala ID          | HID Indala   | __drawID           |
| 11 | 125KHZ    | AWID ID            | AWID         | __drawID           |
| 12 | 125KHZ    | IO Prox ID         | IoProx       | __drawID           |
| 13 | 125KHZ    | G-Prox II ID       | G-Prox       | __drawID           |
| 14 | 125KHZ    | Securakey ID       | SecuraKey    | __drawID           |
| 15 | 125KHZ    | Viking ID          | Viking       | __drawID           |
| 16 | 125KHZ    | Pyramid ID         | Pyramid      | __drawID           |
| 17 | 13.56MHZ  | Legacy             | iCLASS       | __draw_iclass      |
| 18 | 13.56MHZ  | None               | iCLASS       | __draw_iclass      |
| 19 | 13.56MHZ  | ISO15693 ICODE     | ICODE        | __drawID           |
| 20 | 13.56MHZ  | Legic MIM256       | Legic        | __drawLEGIC_MIM256 |
| 21 | 13.56MHZ  | Felica             | Felica       | __drawFelica       |
| 22 | 13.56MHZ  | ISO14443-B         | STR512       | __draw14B          |
| 23 | 125KHZ    | None               | T5577        | __drawT55xx        |
| 24 | 125KHZ    | None               | EM4305       | __drawEM4x05       |
| 25 | 13.56MHZ  | M1 Mini 0.3K       | MIFARE       | __drawM1           |
| 26 | 13.56MHZ  | M1 Mini 0.3K       | MIFARE       | __drawM1           |
| 27 | 13.56MHZ  | Topaz              | TOPAZ        | __drawTopaz        |
| 28 | 125KHZ    | Animal ID          | FDX-B        | __drawID           |
| 29 | 125KHZ    | GALLAGHER ID       | Gallagher    | __drawID           |
| 30 | 125KHZ    | Jablotron ID       | Jablotron    | __drawID           |
| 31 | 125KHZ    | KERI ID            | Keri         | __drawID           |
| 32 | 125KHZ    | NEDAP ID           | Nedap        | __drawID           |
| 33 | 125KHZ    | Noralsy ID         | Noralsy      | __drawID           |
| 34 | 125KHZ    | PAC/Stanley ID     | PAC/Stanley  | __drawID           |
| 35 | 125KHZ    | Paradox ID         | Paradox      | __drawID           |
| 36 | 125KHZ    | Presco ID          | Presco       | __drawID           |
| 37 | 125KHZ    | Visa2000 ID        | Visa2000     | __drawID           |
| 38 | 125KHZ    | Hitag              | HITAG        | __drawID           |
| 39 | 13.56MHZ  | DESFire            | MIFARE       | __drawTopaz        |
| 40 | 13.56MHZ  | ISO/IEC 14443-A    | ISO14443-A   | __drawTopaz        |
| 41 | 13.56MHZ  | M1 S70 4K (7B)    | MIFARE       | __drawM1           |
| 42 | 13.56MHZ  | M1 S50 1K (7B)    | MIFARE       | __drawM1           |
| 43 | 13.56MHZ  | None               | MF POSSIBLE  | __drawM1           |
| 44 | 13.56MHZ  | None               | MF POSSIBLE  | __drawM1           |
| 45 | 125KHZ    | NexWatch ID        | NexWatch     | __drawID           |
| 46 | 13.56MHZ  | ISO15693 ST SA     | ISO15693     | __drawID           |
| 47 | 13.56MHZ  | iCLASS SE          | iCLASS       | __draw_iclass      |

### Tag Type Key Names (tagtypes module constants)

From template_strings.txt, each numeric tag ID maps to a string key used by `tagtypes`:

| ID | Key Constant       |
|----|-------------------|
| 0  | M1_S70_4K_4B      |
| 1  | M1_S50_1K_4B      |
| 2  | ULTRALIGHT        |
| 3  | ULTRALIGHT_C      |
| 4  | ULTRALIGHT_EV1    |
| 5  | NTAG213_144B      |
| 6  | NTAG215_504B      |
| 7  | NTAG216_888B      |
| 8  | EM410X_ID         |
| 9  | HID_PROX_ID       |
| 10 | INDALA_ID         |
| 11 | AWID_ID           |
| 12 | IO_PROX_ID        |
| 13 | GPROX_II_ID       |
| 14 | SECURAKEY_ID      |
| 15 | VIKING_ID         |
| 16 | PYRAMID_ID        |
| 17 | ICLASS_LEGACY     |
| 18 | ICLASS_ELITE      |
| 19 | ISO15693_ICODE    |
| 20 | LEGIC_MIM256      |
| 21 | FELICA            |
| 22 | ISO14443B         |
| 23 | T55X7_ID          |
| 24 | EM4305_ID         |
| 25 | M1_MINI           |
| 26 | M1_MINI           |
| 27 | TOPAZ (N/A)       |
| 28 | FDXB_ID           |
| 29 | GALLAGHER_ID      |
| 30 | JABLOTRON_ID      |
| 31 | KERI_ID           |
| 32 | NEDAP_ID          |
| 33 | NORALSY_ID        |
| 34 | PAC_ID            |
| 35 | PARADOX_ID        |
| 36 | PRESCO_ID         |
| 37 | VISA2000_ID       |
| 38 | HITAG2_ID         |
| 39 | MIFARE_DESFIRE    |
| 40 | HF14A_OTHER       |
| 41 | M1_S70_4K_7B      |
| 42 | M1_S50_1K_7B      |
| 43 | M1_POSSIBLE_4B    |
| 44 | M1_POSSIBLE_7B    |
| 45 | NEXWATCH_ID       |
| 46 | ISO15693_ST_SA    |
| 47 | ICLASS_SE         |

---

## 3. Internal Draw Functions

All draw functions share the same signature pattern from decompilation:
```python
def __drawXxx(data: dict, parent: Canvas) -> None
```

They are **not exported** -- they are module-private, referenced only via TYPE_TEMPLATE tuples.

### 3.1. Draw Function Inventory (16 functions)

From decompiled function names (ordered by Cython index):

| Cython Index | Function Name         | Address    | Used By Tag Types            |
|-------------|----------------------|------------|------------------------------|
| 3           | `__drawFinal`        | 0x000266c0 | Low-level shared renderer    |
| 5           | `__drawFinalByData`  | 0x00025a78 | Low-level shared renderer    |
| 7           | `__drawDataLines`    | 0x00024ba8 | Low-level shared renderer    |
| 9           | `__drawM1`           | 0x00023e68 | 0,1,25,26,41,42,43,44        |
| 11          | `__drawMFU`          | 0x000236b0 | 2,3,4,5,6,7                 |
| 13          | `__drawID`           | 0x00022880 | 8-16,19,28-38,45,46         |
| 15          | `__drawEM4x05`       | 0x00021f60 | 24                          |
| 17          | `__drawT55xx`        | 0x00021640 | 23                          |
| 19          | `__drawLEGIC_MIM256` | 0x00020d20 | 20                          |
| 21          | `__drawFelica`       | 0x00020568 | 21                          |
| 23          | `__draw14B`          | 0x0001fdb0 | 22                          |
| 25          | `__drawTopaz`        | 0x0001f490 | 27,39,40                    |
| 27          | `__draw_iclass`      | 0x0001ea88 | 17,18,47                    |

**Low-level helpers** (not directly in TYPE_TEMPLATE, called by draw functions above):
- `__drawFinal(parent, title, frequency, canvas)` -- renders the common header block
- `__drawFinalByData(data, parent)` -- renders using a data dict for TYPE_TEMPLATE lookup
- `__drawDataLines(parent, ...)` -- renders data line items below the header

### 3.2. __drawFinal -- Common Header Renderer

**Signature** (decompiled at `0x000266c0`, 4 parameters):
```python
def __drawFinal(parent, title, frequency, canvas) -> None
```

**Behavior** from decompiled code:
1. Increments reference on `title`
2. Gets `canvas.delete` and calls it (clears previous content)
3. Creates a new `dict` with drawing kwargs:
   - Sets `text` key to `parent` (the text content)
   - Sets `font` key to a font string constant (see Fonts below)
   - Sets `anchor` key  
   - Sets `justify` key
4. Calls `font.get_font_force_en()` to get the appropriate font object
5. Calls `canvas.create_text(x, y, **kwargs)` to draw:
   - The family name in large bold font (`mononoki 22 bold`)
   - The display name line
   - The frequency line using format string `'Frequency: {}'`

### 3.3. __drawM1 -- MIFARE Classic Renderer

**Decompiled at** `0x00023e68`. Takes `(data, parent)`.

**Renders**:
1. Calls `__drawFinal` with the family/frequency from TYPE_TEMPLATE
2. Gets `font.get_font_force_en()` for data lines
3. Reads `data['uid']` and renders `'UID: {}'`
4. Checks for `'sak'` key in data:
   - If `'sak'` present: renders `'SAK: {}  {}: {}'` (SAK value + ATQA label + ATQA value)
   - Format pattern from strings: `'SAK: {}  {}: {}'` and `'SAK: {} {}: {}'`
5. Checks data length (`PyObject_Size`):
   - If data has < 7 fields: uses compact layout
   - Otherwise: uses extended layout with `__drawDataLines`
6. Reads `data['nameStr']` to get the ATQA label string
7. Reads `data['atqa']` for the ATQA value

**Real device screenshot (scan_tag_scanning_5.png) confirms layout**:
```
     MIFARE              <- family (mononoki 22 bold)
  M1 S50 1K (4B)         <- display_name
  Frequency: 13.56MHZ    <- frequency line
  UID: 3AF73501           <- uid line
  SAK: 08  ATQA: 0004    <- sak + atqa line
```

### 3.4. __drawMFU -- MIFARE Ultralight / NTAG Renderer

**Decompiled at** `0x000236b0`. Takes `(data, parent)`.

Renders similarly to __drawM1 but for Ultralight/NTAG tags. Shows UID, and type-specific
fields. Used for tag types 2-7 (Ultralight, Ultralight C, Ultralight EV1, NTAG213/215/216).

### 3.5. __drawID -- LF ID Tag Renderer

**Decompiled at** `0x00022880`. Takes `(data, parent)`.

The most widely used draw function (covers 25+ LF tag types plus ISO15693).

**Renders**:
1. Calls `__drawFinal` for the header
2. Reads `data['lines']` -- an array/list of data lines
3. Calls `__drawDataLines` to render each line
4. For some tag types, formats special fields:
   - `'Modulate: {}'` -- modulation info (from `data['modulate']`)
   - `'Chipset: {}'` -- chipset info (from `data['chipset']`)
   - `'FC,CN: {},{}` -- facility code and card number (from `data['fc_cn']`)

### 3.6. __draw_iclass -- iCLASS Renderer

**Decompiled at** `0x0001ea88`. Takes `(data, parent)`.

**Renders**:
1. Calls `__drawFinal` for the header
2. Reads `data['manufacturer']` -- manufacturer string
3. Checks if `data['manufacturer']` equals `'unknown'`
   - If `'unknown'`: sets a simplified display string
4. Checks for `'blck7'` key in data (block 7 data)
   - If present and non-empty: shows block 7 content
5. Sets `data['nameStr']` to `'Elite/SE/SEOS'` or `'Legacy'` based on type
6. Reads `data['lines']` for additional data lines
7. Calls `__drawDataLines` for the data section

**Special iCLASS handling**: The `'Elite/SE/SEOS'` string in template_strings.txt is used
for iCLASS Elite (type 18) and iCLASS SE (type 47) tags.

### 3.7. __drawT55xx -- T5577 Renderer

**Decompiled at** `0x00021640`. Takes `(data, parent)`.

Renders T5577 writable tag info. T5577 (type 23) has `display_name = None` in TYPE_TEMPLATE
because it is a writable blank tag. Renders block data from `data['lines']`.

### 3.8. __drawEM4x05 -- EM4305 Renderer

**Decompiled at** `0x00021f60`. Takes `(data, parent)`.

Renders EM4305 writable tag info. Similar to T5577 renderer. EM4305 (type 24) has
`display_name = None`.

### 3.9. __drawLEGIC_MIM256 -- LEGIC Renderer

**Decompiled at** `0x00020d20`. Takes `(data, parent)`.

Renders LEGIC MIM256 (type 20) tag info.

### 3.10. __drawFelica -- FeliCa Renderer

**Decompiled at** `0x00020568`. Takes `(data, parent)`.

Renders FeliCa (type 21) tag info.

### 3.11. __draw14B -- ISO14443-B Renderer

**Decompiled at** `0x0001fdb0`. Takes `(data, parent)`.

Renders ISO14443-B / STR512 (type 22) tag info. Reads `data['atqb']` for the ATQB response.

### 3.12. __drawTopaz -- Topaz / DESFire / HF14A Other Renderer

**Decompiled at** `0x0001f490`. Takes `(data, parent)`.

Shared renderer for Topaz (27), DESFire (39), and ISO/IEC 14443-A "other" (40).
These are HF tags that don't have a specialized renderer.

### 3.13. __drawDataLines -- Multi-line Data Renderer

**Decompiled at** `0x00024ba8`. Takes `(parent, ...)` with variable args.

**Behavior** (from decompiled code):
1. Iterates over a list of data items
2. For each non-None item:
   - Gets `font.get_font_force_en()` for rendering
   - Creates a `dict` with kwargs: `{text: item, font: ..., anchor: 'w', justify: 'left'}`
   - Calls `parent.create_text(x, y, **kwargs)` for each line
   - Increments y-coordinate for next line

This is the workhorse that renders the multi-line data section below the header.

---

## 4. Rendering Layout

Based on the real device screenshot and decompiled string constants:

### Screen Layout (240x240 display)

```
+----------------------------------+
| [Title Bar - "Scan Tag"]         |  <- Set by activity, not template
+----------------------------------+
|                                  |
|          MIFARE                  |  <- Family name (mononoki 22 bold, centered)
|       M1 S50 1K (4B)            |  <- Display name (mononoki 14 bold)
|   Frequency: 13.56MHZ           |  <- Frequency line (mononoki 13)
|   UID: 3AF73501                  |  <- Data line 1 (mononoki 13)
|   SAK: 08  ATQA: 0004           |  <- Data line 2 (mononoki 13)
|                                  |
+----------------------------------+
| [Rescan]           [Simulate]    |  <- Set by activity, not template
+----------------------------------+
```

### Fonts (from decompiled strings)

| Constant           | Usage                          |
|-------------------|-------------------------------|
| `mononoki 22 bold` | Family name (title line)      |
| `mononoki 14 bold` | Display name (subtitle line)  |
| `mononoki 13`      | Data lines (UID, SAK, etc.)  |

Note: The module calls `font.get_font_force_en()` to obtain these font objects, ensuring
English-locale fonts are used regardless of the device language setting.

### Text Anchoring

From decompiled strings:
- `anchor` parameter used in `create_text()` calls
- `justify` parameter: `'left'` for data lines
- Family name appears centered; data lines left-aligned

---

## 5. Format Strings (All Constants)

From decompiled STR@ entries and template_strings.txt:

| String                | Usage                                      |
|----------------------|-------------------------------------------|
| `'Frequency: {}'`    | Frequency line, `.format(freq)`           |
| `'UID: {}'`          | UID display line                          |
| `'SAK: {}  {}: {}'`  | SAK + dynamic label + value (e.g. ATQA)   |
| `'SAK: {} {}: {}'`   | Alternate SAK format (single space)       |
| `'ATQA: {}'`         | ATQA display line (standalone)            |
| `'Modulate: {}'`     | Modulation type (LF tags)                 |
| `'Chipset: {}'`      | Chipset info (LF tags)                    |
| `'FC,CN: {},{}' `    | Facility Code + Card Number (LF ID tags)  |
| `'Elite/SE/SEOS'`    | iCLASS subtype label                     |
| `'unknown'`          | Placeholder for unknown manufacturer      |
| `'Legacy'`           | iCLASS Legacy subtype label              |

### Regex Pattern

From template_strings.txt:
- `'[a-fA-F0-9 -]+'` -- used to validate/match hex data strings (UIDs, keys, etc.)

---

## 6. Data Dict Keys (Interface from scan.so)

The `data` parameter passed to `draw()` is a dict produced by `scan.so` callbacks.
From decompiled attribute access patterns and template_strings.txt:

### Common Keys (all tag types)

| Key          | Type   | Description                                    |
|-------------|--------|------------------------------------------------|
| `'type'`    | int    | Tag type ID (0-47)                             |
| `'title'`   | str    | Activity title string                          |
| `'nameStr'` | str    | ATQA label or type-specific label              |
| `'typStr'`  | str    | Type descriptor string                         |

### HF Tag Keys (MIFARE, Ultralight, NTAG, etc.)

| Key          | Type   | Description                                    |
|-------------|--------|------------------------------------------------|
| `'uid'`     | str    | Tag UID as hex string                          |
| `'sak'`     | str    | SAK byte as hex                                |
| `'atqa'`    | str    | ATQA bytes as hex                              |
| `'data'`    | varies | Raw tag data                                   |
| `'name'`    | str    | Tag name from PM3 output                       |

### LF Tag Keys (EM410x, HID, Indala, etc.)

| Key           | Type   | Description                                   |
|--------------|--------|-----------------------------------------------|
| `'lines'`    | list   | List of data line strings to display          |
| `'modulate'` | str    | Modulation type string                        |
| `'chipset'`  | str    | Chipset identification string                 |
| `'fc_cn'`    | str    | Facility code + card number                   |

### iCLASS-Specific Keys

| Key              | Type   | Description                                |
|-----------------|--------|--------------------------------------------|
| `'manufacturer'` | str    | Manufacturer name (or `'unknown'`)         |
| `'blck7'`        | str    | Block 7 data hex string                    |
| `'chip'`         | str    | Chip type identifier                       |

### ISO14443-B Keys

| Key      | Type   | Description                                    |
|---------|--------|------------------------------------------------|
| `'atqb'` | str    | ATQB response data                             |

### T5577 / EM4305 Keys

| Key      | Type   | Description                                    |
|---------|--------|------------------------------------------------|
| `'lines'` | list | Block data lines                               |

---

## 7. How template.so Receives Data from scan.so

### Call Chain

```
scan.so                          activity_main.py                 template.so
--------                         ----------------                 -----------
onScanFinish(result)  ------>   _showFoundState(result)  ------>  template.draw(typ, data, canvas)
                                                                       |
                                                                       v
                                                                  TYPE_TEMPLATE[typ]
                                                                       |
                                                                       v
                                                                  __drawXxx(data, canvas)
                                                                       |
                                                                       v
                                                                  __drawFinal(...)
                                                                  __drawDataLines(...)
                                                                  canvas.create_text(...)
```

### From activity_main.py (ground truth code):

```python
def _showFoundState(self, result):
    tag_type = result.get('type', -1)
    canvas = self.getCanvas()
    if canvas is not None:
        import template, executor
        template.draw(tag_type, result, canvas)
```

And for cleanup:
```python
import template
template.dedraw(canvas)
```

### Data Flow

1. `scan.so` runs the PM3 scan sequence (hfsearch/lfsearch)
2. Parser modules (hf14ainfo, hfmfread, etc.) extract tag data
3. `scan.so` builds a result dict with tag type, UID, SAK, ATQA, etc.
4. `scan.so` calls back to the activity with this dict
5. Activity calls `template.draw(typ, data, canvas)`
6. `template.draw()` looks up the draw function in TYPE_TEMPLATE
7. The draw function renders all fields to the canvas using `create_text()`
8. When the user leaves the scan result screen, activity calls `template.dedraw(canvas)`

---

## 8. Draw Function to Tag Type Mapping Summary

| Draw Function       | Tag Types                                          | Category           |
|--------------------|---------------------------------------------------|--------------------|
| `__drawM1`         | 0, 1, 25, 26, 41, 42, 43, 44                     | MIFARE Classic     |
| `__drawMFU`        | 2, 3, 4, 5, 6, 7                                 | Ultralight / NTAG  |
| `__drawID`         | 8-16, 19, 28-38, 45, 46                          | LF ID + ISO15693   |
| `__draw_iclass`    | 17, 18, 47                                        | iCLASS             |
| `__drawLEGIC_MIM256` | 20                                              | LEGIC              |
| `__drawFelica`     | 21                                                | FeliCa             |
| `__draw14B`        | 22                                                | ISO14443-B         |
| `__drawT55xx`      | 23                                                | T5577 writable     |
| `__drawEM4x05`     | 24                                                | EM4305 writable    |
| `__drawTopaz`      | 27, 39, 40                                        | Topaz/DESFire/Other|

---

## 9. Implementation Notes

### For Reimplementation

1. **TYPE_TEMPLATE is the routing table**: `draw()` is a simple dispatcher. The real logic
   is in the per-type `__drawXxx` functions.

2. **All rendering goes through tkinter Canvas**: Uses `canvas.create_text()` with kwargs
   dicts for font, anchor, justify, text.

3. **Font module dependency**: Calls `font.get_font_force_en()` to force English-locale
   font rendering (monospace mononoki in 3 sizes).

4. **resources module dependency**: Used for locale-aware string retrieval in some paths.

5. **tagtypes module dependency**: `create_by_parent()` uses `tagtypes` to convert type IDs
   to display-name strings.

6. **re module**: The regex pattern `'[a-fA-F0-9 -]+'` is used for hex data validation.

7. **Cython compilation note**: Original source was `template.py` compiled with Cython 0.29.21.
   The `__pyx_pymod_exec_template` initialization function timed out during Ghidra decompilation,
   but all draw functions and the TYPE_TEMPLATE structure are fully recovered.

8. **dedraw() clears three layers**: Removes title/family text, frequency line, and data
   lines via `canvas.delete()` with coordinate-based tags.

### Data Dict Contract

The `data` dict **must** contain at minimum:
- The keys expected by the specific `__drawXxx` function for the given tag type
- Missing keys will cause `KeyError` / `PyObject_GetItem` failures
- The `'type'` key is used by `draw()` for TYPE_TEMPLATE lookup, not by the draw functions themselves

### Display Name = None

Tag types 18 (iCLASS Elite), 23 (T5577), 24 (EM4305), 43 (MF POSSIBLE 4B), and
44 (MF POSSIBLE 7B) have `display_name = None`. These are either writable blanks or
ambiguous scan results. Their draw functions handle the None case internally.
