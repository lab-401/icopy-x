##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Shared native Canvas notices and log lists; no I/O or navigation ownership.

Screen rows are (message ID/template, color[, visibility key]). Visibility is
an explicit boolean from the caller; missing values never imply a verdict.
"""

TEXT = '#222222'
ERROR = '#B91C1C'
BLUE = '#1647D6'
LOG_ROWS = 5

NOTICE_SCREENS = {
    'auto_read_failed': (
        (1023, TEXT), (1006, ERROR),
        ('Saved scans: {saved}/{total}', TEXT), ('Retry scan {step}', TEXT)),
    'auto_status': ((1005, ERROR), ('$error', TEXT)),
    'auto_no_tag': ((1026, '#FF0000'),),
    'auto_report_retry': (('$title', ERROR), ('$error', TEXT)),
    'auto_report_prompt': (
        (1003, TEXT), (1029, TEXT), (1001, TEXT)),
    'auto_report_saved': ((1019, TEXT), (1001, TEXT), ('$filename', TEXT)),
    'auto_report_discarded': (('Report discarded', TEXT), ('No report saved', TEXT)),
    'auto_report_done_error': (
        ('Report save failed', TEXT), ('$error', TEXT), ('Back to retry', TEXT)),
    'auto_unavailable': (
        ('Auto Scan capture', TEXT), ('not implemented yet.', TEXT),
        ('Scans selected: {total}', BLUE)),
    'delete_log_none': (('No logs selected', '#C62828'), ('Select logs to delete', None)),
    'delete_log_done': (('Logs deleted successfully', '#24813E'), ('Deleted: {deleted} logs', None)),
    'delete_log_error': (('Log delete failed', '#C62828'), ('$error', None)),
}


def notice_rows(name, params, translate, message):
    """Resolve trusted templates before inserting data; never format data twice."""
    rows = []
    for spec in NOTICE_SCREENS[name]:
        text, color = spec[:2]
        if len(spec) == 3 and not params.get(spec[2], False):
            continue
        if isinstance(text, str) and text.startswith('$'):
            value = params[text[1:]]
        else:
            value = translate(message(text)).format(**params)
        rows.append((value, color))
    return rows


def draw_notice(canvas, tag, lines, colors, translate, message, layout='notice', page=0):
    """Measure translated notices and paginate without dropping diagnostic text."""
    from tkinter import font as tkfont
    from _dump_diff_2_lib.screen_catalog import text_rows
    measure=tkfont.Font(family='Courier New',size=12).measure
    translated=[str(translate(message(value))) for value in lines]
    canvas.delete(tag)
    canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
    if layout == 'delete' and all('\n' not in value and measure(value)<=222 for value in translated):
        # Preserve the existing two-label layout, including multiline diagnostics.
        for y, value, color in zip((91, 125), lines, colors):
            options = {'fill': color} if color is not None else {}
            canvas.create_text(120, y, text=translate(message(value)), anchor='center',
                               font=('Courier New', 11), tags=tag, **options)
        return {'text':'\n'.join(translated),'pages':1,'page':0}
    rows = []
    for i, value in enumerate(translated):
        color = colors[i] if colors and i < len(colors) else TEXT
        rows.extend((line, color or TEXT) for line in text_rows(value,measure))
    pages=[rows[i:i+6] for i in range(0,len(rows),6)] or [[]]
    page=max(0,min(page,len(pages)-1));visible=pages[page]
    y = 85 if 2 <= len(visible) <= 3 else 62 if len(visible)==4 else 43
    if len(visible)==1:
        y=(40+200-tkfont.Font(family='Courier New',size=12).metrics('linespace'))/2
    for i, (line, color) in enumerate(visible):
        canvas.create_text(120, y+i*19, text=line, anchor='n', fill=color,
                           font=('Courier New', 12), tags=tag)
    if len(pages)>1:
        canvas.create_text(120,190,text='Page {}/{}'.format(page+1,len(pages)),anchor='center',fill=BLUE,font=('Courier New',9),tags=tag)
        if page:canvas.create_text(235,43,text='▲',anchor='ne',fill=BLUE,font=('Arial',9),tags=tag)
        if page+1<len(pages):canvas.create_text(235,198,text='▼',anchor='se',fill=BLUE,font=('Arial',9),tags=tag)
    return {'text':'\n'.join(line for line,_ in rows),'pages':len(pages),'page':page}


def log_name_window(name, delete=False):
    """Return measured character capacity for the same font/prefix as the list."""
    from tkinter import font as tkfont
    measure = tkfont.Font(family='Courier New', size=11 if delete else 12).measure
    prefix = ' [x] ' if delete else '> '
    # Keep both text and native arrow inside the available horizontal area.
    available = 230 - (10 if delete else 12) - measure(prefix)
    capacity = 0
    for i in range(1, len(name)+1):
        if measure(name[:i]) > available:
            break
        capacity = i
    return max(1, capacity)


def log_name_offset(name, offset, delete=False):
    """Clamp scrolling using a suffix which fits, including variable-width text."""
    from tkinter import font as tkfont
    measure = tkfont.Font(family='Courier New', size=11 if delete else 12).measure
    available = 230 - (10 if delete else 12) - measure(' [x] ' if delete else '> ')
    last = 0
    while last < len(name) and measure(name[last:]) > available:
        last += 1
    return max(0, min(offset, last)), last


def draw_log_list(canvas, tag, files, cursor, display_name, scroll, translate,
                  selected=None):
    """One layout for Read/Delete Logs. selected=None means read-only list."""
    delete = selected is not None
    canvas.delete(tag)
    canvas.create_rectangle(0, 49, 239, 200, fill='white', outline='', tags=tag)
    if not files:
        for y, text, color in ((89, 'No logs found', '#C62828'),
                               (116, 'No saved logs', TEXT), (137, 'available', TEXT)):
            canvas.create_text(120, y, text=translate(text), anchor='center',
                               fill=color, font=('Courier New', 12), tags=tag)
        return
    start = cursor // LOG_ROWS * LOG_ROWS
    for row, path in enumerate(files[start:start+LOG_ROWS]):
        active = start+row == cursor
        y = 57+row*23
        if active:
            canvas.create_rectangle(8, y-3, 232, y+19, fill='#D7E7D8', outline='', tags=tag)
        name = display_name(path) + ('' if delete else ' ')
        offset, last = log_name_offset(name, scroll if active else 0, delete)
        visible = name[offset:offset+log_name_window(name[offset:], delete)]
        prefix = (' [x] ' if path in selected else ' [ ] ') if delete else ('> ' if active else '  ')
        canvas.create_text(10 if delete else 12, y, text=prefix+visible,
                           anchor='nw', font=('Courier New', 11 if delete else 12), tags=tag)
        if delete and active and last:
            if offset < last:
                canvas.create_text(5, y+1, text='▶', anchor='nw', fill='#00BFFF', font=('Arial', 9), tags=tag)
            if offset:
                canvas.create_text(235, y+1, text='◀', anchor='ne', fill='#00BFFF', font=('Arial', 9), tags=tag)
    if delete:
        canvas.create_text(120, 176, text=translate('OK - Select/Deselect'), anchor='center',
                           fill=BLUE, font=('Courier New', 10), tags=tag)
    canvas.create_text(120, 190, text=translate('Page {}/{}'.format(
        start//LOG_ROWS+1, (len(files)+LOG_ROWS-1)//LOG_ROWS)), anchor='center',
        fill=BLUE, font=('Courier New', 10), tags=tag)


# Original entry actions, dispatched after plugin-owned canvas cleanup.
SCREEN_ENTRIES = {'init': 'run:init', 'types': 'call:draw_types', 'picker': 'call:draw_picker', 'error': 'call:draw_compare_error', 'details_first': 'call:draw_details', 'details_middle': 'call:draw_details', 'details_last': 'call:draw_details', 'details_single': 'call:draw_details', 'need_two': 'call:show_need_two_timed', 'compare_mode': 'call:draw_compare_mode', 'identical_details': 'call:show_changes_safe', 'different_details': 'call:show_changes_safe', 'start_menu': 'call:draw_start', 'auto_options': 'call:draw_auto_options', 'auto_unavailable': 'call:draw_auto_unavailable', 'auto_capture': 'call:draw_auto_capture', 'auto_no_tag': 'call:draw_auto_no_tag', 'auto_status': 'call:draw_auto_status', 'auto_result': 'call:draw_auto_result', 'auto_info': 'call:draw_auto_info', 'auto_report_prompt': 'call:draw_auto_report_prompt', 'auto_report_done': 'call:draw_auto_report_done', 'auto_unsupported': 'call:draw_auto_unsupported', 'auto_report_retry': 'call:draw_auto_report_retry', 'auto_capture_next': 'call:draw_auto_capture', 'auto_actions': 'call:draw_auto_actions', 'auto_report_save_busy': 'run:auto_report_save_with_delay', 'auto_exit_busy': 'run:auto_report_discard', 'auto_log_list': 'call:draw_auto_log_list', 'auto_log_view': 'call:draw_auto_log_view', 'delete_log_list': 'call:draw_delete_log_list', 'delete_log_none': 'call:draw_delete_log_none', 'delete_log_done': 'call:draw_delete_log_done', 'delete_log_error': 'call:draw_delete_log_error', 'auto_log_empty': 'call:draw_auto_log_list', 'delete_log_empty': 'call:draw_delete_log_list', 'auto_read_failed': 'call:draw_auto_read_failed'}


"""Measured, translated field pages shared by diagnostic and error screens.

No RF, file I/O, status inference or navigation. Values remain data; only
authored text is translated. Complete HEX groups stay on one page.
"""

def text_rows(value, measure, width=222):
    rows = []
    for paragraph in str(value).split('\n'):
        line = ''
        for word in paragraph.split():
            trial = (line+' '+word).strip()
            if line and measure(trial) > width:
                rows.append(line); line = ''
            # A long diagnostic token is continued without dropping characters.
            while measure(word) > width:
                end = 1
                while end < len(word) and measure(word[:end+1]) <= width:
                    end += 1
                rows.append(word[:end]); word = word[end:]
            line = (line+' '+word).strip()
        rows.append(line)
    return rows or ['']


def analysis_notice_lines(translate):
    """Wrap complete translated sentences using the actual content font."""
    from tkinter import font as tkfont
    measure = tkfont.Font(family='Courier New', size=12).measure
    sentences = ('Detection is not proof of protection.',
                 'No match does not prove its absence.')
    return [line for sentence in sentences
            for line in text_rows(translate(sentence), measure, 222)]


def row_positions(rows, previous=True, size=12):
    """Reserve a blank row only when the first text intersects the up arrow."""
    from tkinter import font as tkfont
    font=tkfont.Font(family='Courier New',size=size)
    arrow=tkfont.Font(family='Arial',size=9)
    y=43 if rows and rows[0][0]=='heading' else (40+200-font.metrics('linespace'))/2 if len(rows)==1 else 85 if len(rows)<=3 else 62 if len(rows)==4 else 43
    result=[];prior=None
    for row in rows:
        kind,label,value=row[:3]
        if kind=='hex' and prior=='hex':y+=5
        if y==43 and previous:
            text=label+' '+value if kind in ('pair','hex_pair') else label
            width=font.measure(text)
            left=(240-width)/2 if kind in ('heading','hex','label') else font.measure(' ')
            if left+width+1>235-arrow.measure('▲')-1:
                y+=19
        result.append(y);y+=19;prior=kind
        if kind=='heading' and len(result)==1 and len(rows)==2:
            y=(40+200-font.metrics('linespace'))/2
        if kind=='heading' and len(result)==1 and 2<=len(rows)-1<=4 and not any(r[0]=='filename' for r in rows):
            y+=19
    return result


def draw_pair(canvas,x,y,label,value,color,face,tag,measure):
    """One left space, grey label, black colon, one space, colored value."""
    name=label.rstrip(' :')
    canvas.create_text(x,y,text=name,anchor='nw',fill='#64748B',font=face,tags=tag)
    colon_x=x+measure(name)
    canvas.create_text(colon_x,y,text=':',anchor='nw',fill='#222222',font=face,tags=tag)
    canvas.create_text(colon_x+measure(': '),y,text=value,anchor='nw',fill=color,font=face,tags=tag)


def pm3_display_fields(result):
    """Present stored PM3 fields once, retaining values, context and severity."""
    import re
    blue, warning, red = '#1647D6', '#E58A19', '#D62636'
    result = result or {}
    status = str(result.get('status') or 'NOT TESTED')
    rows = [('Status:', status, red if status == 'MATCH' else warning if status == 'EXPERIMENTAL' else '#64748B')]
    reason = str(result.get('reason') or '')
    if reason and reason != 'PM3 results; not proof of protection':
        rows.append(('Reason:', reason, blue))
    names = []
    for key, label, color in (('matches', 'Match:', red), ('experimental', 'Experimental:', warning)):
        for entry in result.get(key) or []:
            name = str(entry.get('name') or entry.get('family') or 'Unknown') if isinstance(entry, dict) else str(entry)
            row = (label, name, color)
            if row not in rows:
                rows.append(row)
            names.append(name)
    fields = result.get('fields') or []
    covered = set()
    contexts = list(dict.fromkeys(str(f.get('section') or '') for f in fields))
    context = None
    invalid_sectors = []
    for field in fields:
        match = re.fullmatch(r'Invalid Access Conditions on sector\s+(\d+)', str(field.get('value') or ''), re.I)
        if match:
            invalid_sectors.append(int(match.group(1)))
    sector_row_added = False
    for field in fields:
        section = str(field.get('section') or '')
        label = str(field.get('label') or 'Info')
        value = str(field.get('value') or '')
        covered.add(section + ' / ' + label + ': ' + value)
        if len(contexts) > 1 and section != context:
            rows.append(('Context:', section, blue))
            context = section
        if re.fullmatch(r'Invalid Access Conditions on sector\s+\d+', value, re.I):
            if not sector_row_added:
                ranges = []
                for number in sorted(set(invalid_sectors)):
                    if ranges and number == ranges[-1][1] + 1:
                        ranges[-1][1] = number
                    else:
                        ranges.append([number, number])
                rows.append(('Invalid sectors:', ', '.join(str(a) if a == b else '{}-{}'.format(a, b) for a, b in ranges), red))
                sector_row_added = True
            continue
        # A detected-family sentence repeats the explicit Match rows above.
        if label == 'Info' and value.lower().endswith(' detected'):
            detected = value[:-9].strip()
            parts = [s.strip().lower() for s in detected.split('/')]
            if parts and all(part in [name.lower() for name in names] for part in parts):
                continue
        caution = re.search(r'reported to|can desynchronise|lock you out|anti.?clone counter measurements', value, re.I)
        color = warning if field.get('severity') == 'warning' or caution else blue
        is_hex = (label.lower() == 'card identifier' or
                  re.fullmatch(r'sector\s+\d+\s+blk\s+\d+', label, re.I))
        compact = re.sub(r'\s+', '', value)
        if is_hex and re.fullmatch(r'(?:[0-9a-fA-F]{2})+', compact):
            value = ' '.join(compact[i:i+2].upper() for i in range(0, len(compact), 2))
            rows.append((label.rstrip(':') + ':', value, color, 'hex'))
        else:
            row = (label.rstrip(':') + ':', value, color)
            if row not in rows:
                rows.append(row)
    # Older reports and supplemental MAD diagnostics may have no structured field.
    for note in result.get('diagnostics') or []:
        note = str(note)
        if note not in covered:
            color = warning if re.search(r'warning|possible|candidate|mismatch|invalid|wrong .*crc|not verified|disagree', note, re.I) else blue
            row = ('Diagnostic:', note, color)
            if row not in rows:
                rows.append(row)
    return rows


def field_pages(sections, translate, size=12, limit=6):
    """sections: (title, [(label, value[, color])]); return renderable rows.

    Labels with values and multiline HEX are atomic when they fit. Long prose
    continues with the label repeated, so no detail is silently lost.
    """
    from tkinter import font as tkfont
    measure = tkfont.Font(family='Courier New', size=size).measure
    pages = []
    for title, fields in sections:
        section_start=len(pages)
        title = translate(title)
        heading = [('heading', line, '', '#1647D6') for line in text_rows(title, measure)] if title else []
        capacity = limit-len(heading)
        if capacity < 2:
            raise ValueError('Diagnostic heading too tall')
        current = list(heading)
        for entry in fields:
            label, value = entry[:2]
            color = entry[2] if len(entry)>2 else '#1647D6'
            if str(value).upper() in ('MATCH','INVALID') and color!='#E58A19':color='#D62636'
            elif str(value).upper() in ('EXPERIMENTAL','INVALID / UNKNOWN','CANDIDATE ONLY'):color='#E58A19'
            elif str(value).upper()=='N/A':color='#64748B'
            label = translate(str(label)).rstrip(' :')+':' if label else ''
            value = translate(str(value))
            is_hex = len(entry)>3 and entry[3] in ('hex','hex_compare')
            if is_hex:
                cells=value.split()
                marked=set(entry[4]) if len(entry)>4 else set()
                if entry[3]=='hex_compare' and measure(label+' '+value)<=222:
                    group=[('hex_pair',label,value,color,tuple(sorted(marked)))]
                else:
                    group=[('label',label,'','#64748B')]+[
                        ('hex',' '.join(cells[i:i+8]),'',color,tuple(j-i for j in marked if i<=j<i+8)) for i in range(0,len(cells),8)]
                if any(measure(r[1])>230 for r in group):
                    raise ValueError('HEX row exceeds screen')
            elif measure(label+' '+value) <= 222 and '\n' not in value:
                group = [('pair',label,value,color)]
            else:
                labels = [('label',line,'','#64748B') for line in text_rows(label,measure)] if label else []
                values = [('text',line,'',color) for line in text_rows(value,measure)]
                if len(labels)+len(values) <= capacity:
                    group = labels+values
                else:
                    if len(current)>len(heading):pages.append(current);current=list(heading)
                    room=max(1,capacity-len(labels))
                    for start in range(0,len(values),room):
                        pages.append(heading+labels+values[start:start+room])
                    continue
            if len(current)+len(group)>limit or row_positions(current+group,size=size)[-1]+tkfont.Font(family='Courier New',size=size).metrics('linespace')>171:
                pages.append(current);current=list(heading)
            current.extend(group)
        if len(current)>len(heading):
            # Rebalance a trailing one-line field without splitting atomic HEX.
            if (len(current)==len(heading)+1 and current[-1][0]=='pair'
                    and len(pages)>section_start):
                previous=pages[-1]
                if len(previous)>=len(heading)+3 and previous[-1][0]=='pair':
                    balanced=heading+[previous[-1]]+current[len(heading):]
                    if row_positions(balanced,size=size)[-1]+tkfont.Font(family='Courier New',size=size).metrics('linespace')<=171:
                        current=balanced
                        previous.pop()
            pages.append(current)
    return pages


def draw_field_page(canvas, rows, index, total, tag, footer, translate, size=12):
    from tkinter import font as tkfont
    face=('Courier New',size)
    measure=tkfont.Font(family='Courier New',size=size).measure
    canvas.delete(tag)
    canvas.create_rectangle(0,43,239,200,fill='white',outline='',tags=tag)
    for row,y in zip(rows,row_positions(rows,index>0,size)):
        kind,label,value,color=row[:4]
        if kind=='pair':
            width=measure(label+' ')
            x=(240-measure(label+' '+value))/2 if len(rows)==1 else measure(' ')
            draw_pair(canvas,x,y,label,value,color,face,tag,measure)
        elif kind in ('hex','hex_pair'):
            parts=(value if kind=='hex_pair' else label).split()
            x=(240-measure(label))/2
            if kind=='hex_pair':
                left=(240-measure(label+' '+value))/2 if len(rows)==1 else measure(' ')
                draw_pair(canvas,left,y,label,'',color,face,tag,measure)
                x=left+measure(label+' ')
            for byte_index,part in enumerate(parts):
                canvas.create_text(x,y,text=part,anchor='nw',fill='#C62828' if byte_index in row[4] else color,font=face,tags=tag)
                x+=measure(part+' ')
        else:
            center=kind in ('heading','label') or len(rows)==1
            canvas.create_text(120 if center else measure(' '),y,text=label,anchor='n' if center else 'nw',fill=color,font=face,tags=tag)
    canvas.create_text(120,177,text=translate('SRW - '+footer),anchor='center',fill='#1647D6',font=('Arial',9),tags=tag)
    canvas.create_text(120,190,text=translate('Page {}/{}'.format(index+1,total)),anchor='center',fill='#1647D6',font=('Courier New',9),tags=tag)
    if index:canvas.create_text(235,43,text='▲',anchor='ne',fill='#1647D6',font=('Arial',9),tags=tag)
    if index+1<total:canvas.create_text(235,198,text='▼',anchor='se',fill='#1647D6',font=('Arial',9),tags=tag)
