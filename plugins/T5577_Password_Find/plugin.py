##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Copyright (c) 2026: ETOILE401 SAS & https://github.com/quantum-x/
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

##########################################################################
# T5577 PASSWORD FIND - MAIN PLUGIN (iCopy-X / iCopy-XS)
##########################################################################
# Purpose:
#   - Provides Dictionary, Password from Date, Date + Dictionary and
#     Set Password workflows through the native iCopy-X/XS UI state machine.
#   - Accepts a start/end date and the YYYYMMDD or DDMMYYYY password format.
#   - Validates dates and counts unique dictionary/date candidates before scan.
#   - Checks firmware compatibility and T55xx password-protection status.
#   - Uploads bounded key batches into PM3 SPIFFS and uses ARM-side T55xx
#     password checking; accepts only a verified password result.
#   - Performance: 1,000 passwords are estimated to take about 4 min 25 s
#     (conservative planning estimate: around 5 min, not a hard limit),
#     using ARM-side lf t55xx chk -m --r0 and batched SPIFFS keys
#     instead of slow client-side checking of each password.
#   - Displays progress, timing estimates, success and error messages.
#   - Supports password management with bounded detect and recovery.
#   - Rejects malformed or conflicting PM3 result fields.
#   - Reads back block 0 using the new key after setting/changing a password;
#     verifies the expected configuration and blocks 1-7 after a wipe.
#   - Keeps Canvas/input operations on the UI thread and RF work on run:.
#   - Cancels between PM3 batches; avoids replaying uncertain write results.
# Dependencies: lib/candidates.py, ui.json, manifest.json, lang/en.json,
#               lang/fr.json, iCopy host/executor PM3 integration.
# Lab401 integration: RF and disk work use run:; short UI updates use call:.
# Requirements: updated iCopy-X/XS software with call: support and
#               newer Iceman PM3 ARM firmware supporting SPIFFS
#               dictionary loading and lf t55xx chk -m --r0.
#               Legacy Lab401 PM3 firmware (including 1.0.90) is unsupported.
##########################################################################
# @copyright (2026) jareckib

import os, re, sys, datetime, threading, hashlib, time
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(HERE,'lib'))
from candidates import KEY,dictionary,priority_alternating,dates,detect_state,verified,read_block
from lib import resources
from time import monotonic
DIC='/mnt/upan/keys/t55xx/t5577_key.dic'
CHK_BATCH='/tmp/.keys/t5577_find_batch.dic'
# ARM firmware accepts at most 8192 bytes = 2048 four-byte keys per batch.
# Keep requests well below the device watchdog and re-estimate after each batch.
CHK_BATCH_INITIAL=127
CHK_BATCH_MIN=32
CHK_BATCH_MAX=500
CHK_BATCH_HARD_MAX=2048
CHK_TARGET_SECONDS=48.0
# Typical ARM chk -m call has sizeable fixed baseline/verification overhead.
CHK_ESTIMATED_OVERHEAD=25.0
CHK_SAFETY_CAP_SECONDS=56.0
CHK_TIMEOUT_MS=65000
SET_DETECT_TIMEOUT_MS=6000  # Bound the initial detect for both scan and Set Password
LOAD_TIMEOUT_MS=18000
MODES=('Dictionary','Password from Date','Date + Dictionary','Set Password')
FIELDS=(('Start year',4),('Start month',2),('Start day',2),('End year',4),('End month',2),('End day',2))

class T5577PasswordFindPlugin:
    def __init__(self,host=None):
        self._reader_blocked=False;self._closed=False;self._info_page=0
        self.host=host;self.index=0;self.mode=0;self._hex=None;self._dec=None
        self.fields=[];self.field=0;self.start=None;self.end=None;self.date_format_index=0
        self.password=None;self.found=None;self.protected=False;self.cancel=threading.Event()
        self._sequence=None;self._seen=set();self._done=0;self._total=0;self._phase='';self._scan_ready=False
        self._prepared_keys=None;self._prepared_total=None
        self._action_index=0;self._pending_action=None;self._verified_block=None;self._old_password=None
        self._chip_type='';self._lf_id='';self._search_note='';self._p1_verified=False
        self._pm3_serial=0;self._pending_batch=None;self._batch_size=CHK_BATCH_INITIAL;self._batch_index=0;self._last_batch_s=None;self._scan_started_mono=None;self._scan_started_wall=None;self._batch_timings=[];self._eta_line="ETA: calculating";self._upper_line="Upper: calculating";self._firmware_notice=''

    def var(self,k,v):self.host.set_var(k,str(v))
    def tr(self,v):
        f=getattr(self.host,'tr',None)
        return f(v) if callable(f) else v
    def error(self,v):
        self._error_full=self.tr(str(v));self.var('error_msg',self._error_full[:21]);return {'status':'error'}
    def pm3(self,cmd,timeout=14000):
        if self._reader_blocked or self._closed:return False, 'Reader unavailable'
        self._pm3_serial+=1
        seq=self._pm3_serial
        start=monotonic()
        try:
            result=self.host.pm3_command(cmd,timeout=timeout)
        except Exception as exc:
            raise
        try:
            success, reply=result
        except (TypeError,ValueError):
            return result
        return result
    def reset_budget(self):
        # Only on an EXPLICIT new user action, never per candidate or retry.
        try:
            import executor
            f=getattr(executor,'resetReworkCount',None)
            if callable(f): f()
        except (ImportError,AttributeError): pass
    def on_destroy(self):
        self._closed=True;self.cancel.set();self.hide_dec();self.hide_hex()
    def _draw_lines(self, lines=(), color='#555555'):
        from tkinter import font as tkfont
        from lib import resources
        c=self.host.getCanvas();tag='_t5577_screen';c.delete(tag)
        c.create_rectangle(0,49,239,198,fill='white',outline='',tags=(tag,'_jr_content'))
        translated=[self.tr(str(v)) for v in lines if v is not None]
        for size in (16,14,12):
            font=resources.get_font(size);face=tkfont.Font(root=c,font=font)
            rows=[]
            for text in translated:
                for para in text.split('\n'):
                    if not para.strip():rows.append('');continue
                    line=''
                    for word in para.split():
                        if line and face.measure(line+' '+word)>220:rows.append(line);line=''
                        while face.measure(word)>220:
                            n=1
                            while n<len(word) and face.measure(word[:n+1])<=220:n+=1
                            rows.append(word[:n]);word=word[n:]
                        line+=(' ' if line else '')+word
                    if line:rows.append(line)
            step=max(19,face.metrics('linespace')+1)
            if len(rows)*step<=130:break
        capacity=max(1,130//step)
        pages=[rows[i:i+capacity] for i in range(0,len(rows),capacity)] or [[]]
        self._info_page=min(getattr(self,'_info_page',0),len(pages)-1)
        shown=pages[self._info_page];y=120-(len(shown)-1)*step/2
        for row in shown:
            value_color='#1647D6' if re.fullmatch(r'[0-9A-Fa-f]{8}',row or '') else color
            pair=re.fullmatch(r'(.*?:)\s*([0-9A-Fa-f]{8})',row)
            if pair:
                label,value=pair.groups();start=(240-face.measure(label+' '+value))/2
                c.create_text(start,y,text=label,anchor='w',font=font,fill='#555555',tags=(tag,'_jr_content'))
                c.create_text(start+face.measure(label+' '),y,text=value,anchor='w',font=font,fill='#1647D6',tags=(tag,'_jr_content'))
            else:c.create_text(120,y,text=row,font=font,fill=value_color,tags=(tag,'_jr_content'))
            y+=step
        if len(pages)>1:
            c.create_text(120,190,text=self.host.tr('Page %d/%d')%(self._info_page+1,len(pages)),font=resources.get_font(9),fill='#1647D6',tags=(tag,'_jr_content'))
    def info_up(self):
        self._info_page=max(0,self._info_page-1);self.show_info()
    def info_down(self):
        self._info_page+=1;self.show_info()
    def clear_screen(self):self.host.getCanvas().delete('_t5577_screen')
    def show_info(self):
        name=getattr(self,'_screen_name','')
        info={
        'not_protected':[self.tr('Password not set'),'',self.tr('No search required')],
        'already_locked':[self.tr('Password already set'),'',self.tr('Remove password first')],
        'unknown':([self.tr('T55xx chip detected'),self.tr('Password may be set'),self.tr('Remove password first'),self.tr('PWD not verified')] if self.mode==3 else [self._search_note or self.tr('LF check complete'),self.tr('Detect: no config'),self.tr('PWD state unknown'),self.tr('Search blocked')]),
        'confirm_locked':[self.tr('Possibly password'),self.tr('protected'),'',self.tr('Continue search?')],
        'scan_warning':[self.tr('WARNING: CHIP DAMAGE'),self.tr('PWD state: unknown'),self.tr('Wrong PWD may damage'),self.tr('the tag! Continue?')],
        'p1_failed':[self.tr('Not a T5577 tag'),self.tr('or damaged tag')],
        'absent':[self.tr('Not a T5577 tag'),self.tr('or damaged tag')],
        'search_failed':[self.tr('T55xx check error'),'',self.tr('Check PM3 connection')],
        'detect_failed':[self.tr('PM3 recovery failed'),self.tr('Check PM3 connection')],
        'not_found':[self.tr('Password not found')],
        'cancelled':[self.tr('Search cancelled')],
        'batch_pause':[self.tr('Batch %d complete')%self._batch_index,self.tr('Checked: %d / %d')%(self._done,self._total),self._eta_line,self._upper_line,self.tr('Next: %d keys')%min(self._batch_size,max(0,self._total-self._done))],
        'date_ready':[getattr(self,'date_start',''),getattr(self,'date_end',''),
                      self.tr('Format: ')+('YYYYMMDD','DDMMYYYY')[self.date_format_index],
                      self.tr('Passwords: ')+str(self._prepared_total or 0),self.tr('Start scanning?')],
        'set_confirm':[self.tr('New: ')+str(self.password or ''),'',self.tr('Protect this tag?')],
        'set_success':[self.tr('Password enabled'),str(self.password or '')],
        'error':[getattr(self,'_error_full',self.tr('Unknown error'))],
        'firmware_notice':[self._firmware_notice or self.tr('Firmware incompatible'), self.tr('Update PM3 firmware'), self.tr('Plugin unavailable')],
        'save_prompt':[self.tr('Password candidate:'),str(self.found or ''),'',self.tr('Save to dictionary?')],
        'saved':[self.tr('Password saved'),self.tr('Dictionary updated')],
        'found_menu':[self.tr('Password: ')+str(self.found or ''),self.tr('Choose operation')],
        'action_confirm':[str(self._pending_action or ''),self.tr('Confirm operation?')],
        'action_success':[str(self._pending_action or ''),self.tr('Success')],
        'action_failure':[self.tr('Operation not verified'),self.tr('Check tag state')],
        'date_summary':[self.tr('Dates generated in RAM')],
        }
        self._draw_lines(info.get(name,[]),'#C62828' if name in ('error','unknown','already_locked','action_failure','confirm_locked','scan_warning','p1_failed','firmware_notice','absent','search_failed','detect_failed') else '#555555')
    def set_screen(self,name):self._screen_name=name;self._info_page=0;self.show_info()
    def draw_action_menu(self):
        names=(self.tr('Remove Password'),self.tr('Change Password'),self.tr('Wipe'),self.tr('Back'))
        c=self.host.getCanvas();tag='_t5577_action';c.delete(tag)
        c.create_rectangle(0,49,239,198,fill='white',outline='',tags=(tag,'_jr_content'))
        c.create_text(120,60,text=self.tr('Password candidate'),font=resources.get_font(12),fill='#1647D6',tags=(tag,'_jr_content'))
        for i,n in enumerate(names):
            y=83+i*22
            if i==self._action_index:c.create_rectangle(6,y-10,234,y+11,fill='#38A757',outline='',tags=(tag,'_jr_content'))
            c.create_text(120,y,text=self.tr(n),anchor='center',font=resources.get_font(12),
                          fill='white' if i==self._action_index else '#555555',tags=(tag,'_jr_content'))
        c.create_text(120,185,text=self.tr('Page 1/1'),font=resources.get_font(10),fill='#1647D6',tags=(tag,'_jr_content'))
    def action_up(self):self._action_index=(self._action_index-1)%4;self.draw_action_menu()
    def action_down(self):self._action_index=(self._action_index+1)%4;self.draw_action_menu()
    def choose_action(self):
        if self._action_index==3:return {'status':'back'}
        self._pending_action=('Remove Password','Change Password','Wipe')[self._action_index]
        if self._action_index==1:return {'status':'new_password'}
        return {'status':'confirm'}
    def begin_action(self):
        self.reset_budget();return {'status':'ok'}


    @staticmethod
    def _firmware_status(output):
        """Use Dump Diff 2's factory signature; do not infer support from client version.

        Fail closed for missing/malformed version text: chk -m requires newer ARM
        firmware and attempting an unsupported command is not a safe fallback.
        """
        raw=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(output or ''))
        os_match=re.search(r'^\s*(?:\[[^]]+\]\s*)?OS[.\s:]+(.*)$',raw,re.I|re.M)
        nikola_match=re.search(r'^\s*(?:\[[^]]+\]\s*)?NIKOLA\s*:\s*(.*)$',raw,re.I|re.M)
        os_version=os_match.group(1).strip() if os_match else ''
        nikola=nikola_match.group(1).strip() if nikola_match else ''
        if re.match(r'^v3\.1(?:\s|$)',nikola) and '2022-06-09' in nikola and '385d892f' in os_version:
            return 'legacy_1090'
        # PM3 ARM, not the Linux client or iCopy OS, must report Iceman.
        if re.search(r'\bIceman\b',os_version,re.I) and '385d892f' not in os_version:
            return 'supported'
        return 'unknown'

    def _check_firmware(self):
        try:
            ok,out=self.pm3('hw version',8000)
        except Exception:
            recovered=self._recover_set_detect()
            self._firmware_notice=self.tr('PM3 version unknown') if recovered else self.tr('PM3 recovery failed')
            return False
        if not ok and self._detect_timed_out(ok,out,8.0):
            recovered=self._recover_set_detect()
            self._firmware_notice=self.tr('PM3 version unknown') if recovered else self.tr('PM3 recovery failed')
            return False
        status=self._firmware_status(out) if ok else 'read_error'
        if status=='supported':
            try:
                chk_ok,chk=self.pm3('lf t55xx chk -h',5000)
                load_ok,load=self.pm3('mem load -h',5000)
                capable=chk_ok and load_ok and '--r0' in chk and re.search(r'(?<!\w)-m\b',chk) and re.search(r'(?<!\w)-t\b',load)
                if capable:return True
                if not chk_ok or not load_ok:self._recover_set_detect()
            except Exception:
                self._recover_set_detect()
            self._firmware_notice=self.tr('Required PM3 commands unavailable')
            return False
        self._firmware_notice=(self.tr('Older PM3 detected') if status=='legacy_1090' else self.tr('PM3 version unknown'))
        return False

    def screen_firmware_notice(self):
        self.set_screen('firmware_notice')

    def do_init(self):
        self.index=0;self.cancel.clear();self.protected=False;self._action_index=0;self._scan_ready=False
        for k in ('error_msg','scan_phase','scan_progress','scan_key','found_password','date_summary','new_password','chip_type','lf_id','search_note','scan_bar','scan_percent','scan_batch','scan_eta','scan_upper'):self.var(k,'')
        self.var('date_format','DDMMYYYY / YYYYMMDD')
        if not self._check_firmware():return {'status':'incompatible'}
        return {'status':'ok'}

    def draw_menu(self):
        c=self.host.getCanvas();tag='_t5577_menu';c.delete(tag)
        c.create_rectangle(0,49,239,198,fill='white',outline='',tags=(tag,'_jr_content'))
        c.create_text(120,60,text=self.tr('Select search mode'),font=resources.get_font(12),fill='#1647D6',tags=(tag,'_jr_content'))
        for i,item in enumerate((self.tr('Dictionary'),self.tr('Password from Date'),self.tr('Date + Dictionary'),self.tr('Set Password'))):
            y=83+i*22
            if i==self.index:c.create_rectangle(6,y-10,234,y+11,fill='#38A757',outline='',tags=(tag,'_jr_content'))
            c.create_text(120,y,anchor='center',text=self.tr(item),font=resources.get_font(12),fill='white' if i==self.index else '#555555',tags=(tag,'_jr_content'))
        c.create_text(120,185,text=self.tr('Page 1/1'),font=resources.get_font(10),fill='#1647D6',tags=(tag,'_jr_content'))
    def draw_date_format_menu(self):
        # Selection is UI-only; RF and dictionary generation remain on run:.
        c=self.host.getCanvas();tag='_t5577_format';c.delete(tag)
        c.create_rectangle(0,49,239,198,fill='white',outline='',tags=(tag,'_jr_content'))
        c.create_text(120,65,text=self.tr('Date format'),font=resources.get_font(12),
                      fill='#1647D6',tags=(tag,'_jr_content'))
        for i,item in enumerate(('YYYYMMDD','DDMMYYYY')):
            y=104+i*30
            if i==self.date_format_index:
                c.create_rectangle(6,y-11,234,y+12,fill='#38A757',outline='',tags=(tag,'_jr_content'))
            c.create_text(120,y,text=item,font=resources.get_font(12),
                          fill='white' if i==self.date_format_index else '#555555',
                          tags=(tag,'_jr_content'))
        c.create_text(120,185,text=self.tr('Page 1/1'),font=resources.get_font(10),
                      fill='#1647D6',tags=(tag,'_jr_content'))

    def clear_date_format_menu(self):
        self.host.getCanvas().delete('_t5577_format')

    def format_up(self):
        self.date_format_index=(self.date_format_index-1)%2
        self.draw_date_format_menu()

    def format_down(self):
        self.date_format_index=(self.date_format_index+1)%2
        self.draw_date_format_menu()

    def choose_date_format(self):
        self.var('date_format',('YYYYMMDD','DDMMYYYY')[self.date_format_index])
        return {'status':'ready'}

    def clear_menu(self):self.host.getCanvas().delete('_t5577_menu')
    def clear_action_menu(self):self.host.getCanvas().delete('_t5577_action')
    def menu_up(self):self.index=(self.index-1)%4;self.draw_menu()
    def menu_down(self):self.index=(self.index+1)%4;self.draw_menu()
    def choose_mode(self):
        self.mode=self.index;self._pending_action=None;self.protected=False;self.cancel.clear();self.reset_budget();self._scan_ready=False
        self._prepared_keys=None;self._prepared_total=None
        if self.mode==3:return {'status':'set'}
        if self.mode in (1,2):
            self.field=0;self.fields=[]
            self.var('date_format','')
            return {'status':'date'}
        return {'status':'scan'}

    def do_p1detect(self):
        """Check Page 1 presence; recover PM3 after any negative result.

        A successful p1detect does not prove the password state. When no
        chip is reported, reset PM3 before the next reader operation.
        """
        self.protected=False
        self._chip_type=''
        self._search_note=''
        self._p1_verified=False
        self.var('chip_type','')
        self.var('search_note','')
        found=False
        failed=False
        try:
            ok,out=self.pm3('lf t55xx p1detect',6000)
            clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',str(out or ''))
            found=bool(ok and re.search(r'\bT55xx chip found!',clean,re.IGNORECASE))
        except Exception:
            failed=True
        if found:
            self._p1_verified=True
            self._chip_type='T55xx'
            self.var('chip_type','T55xx')
            self._search_note='Chipset: T55xx'
            self.var('search_note',self._search_note)
            return {'status':'ok'}
        # Even a normal negative response may precede another read.
        # Reset PM3 as a precaution whenever p1detect did not find a tag.
        if not self._recover_set_detect():
            return {'status':'detect_failed'}
        if failed:
            return self.error(self.tr('P1 detection error'))
        return {'status':'not_found'}

    @staticmethod
    def _detect_timed_out(ok, output, elapsed_s):
        """Treat a silent failed 6s PM3 detect as a timeout, never as PWD proof."""
        if ok:
            return False
        reply=str(output or '')
        return bool(re.search(r'time.?out|unresponsive|offline',reply,re.I)) or (not reply.strip() and elapsed_s>=5.5)

    def _recover_set_detect(self):
        """Reset the returned, idle PM3 command pipeline (never replay RF writes)."""
        try:
            import executor
            restart=getattr(executor,'reworkPM3All',None)
            recovered=restart() is True if callable(restart) else False
            self._reader_blocked=not recovered
            return recovered
        except Exception:
            self._reader_blocked=True
            return False

    def _recover_after_failure(self, message):
        """Report the original failure only after PM3 recovery succeeds.

        A failed recovery stops this action rather than issuing another RF
        command. This cannot guarantee that the firmware has stopped a task.
        """
        if not self._recover_set_detect():
            return {'status':'detect_failed'}
        return self.error(message)

    def do_detect(self):
        """Read unprotected Block 0 before a search; failure is not PWD proof.

        The scan path recovers PM3 only after a silent detect or exception,
        before offering Continue. Set Password retains its own guard.
        """
        scan_mode=self.mode!=3
        t0=monotonic()
        try:
            ok,out=self.pm3('lf t55xx detect',SET_DETECT_TIMEOUT_MS)
        except Exception:
            if not self._recover_set_detect():
                return {'status':'detect_failed'}
            return {'status':'confirm_locked' if scan_mode else 'unknown'}
        clean=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',str(out or ''))
        if self._detect_timed_out(ok,out,monotonic()-t0):
            if not self._recover_set_detect():
                return {'status':'detect_failed'}
            return {'status':'confirm_locked' if scan_mode else 'unknown'}
        chip=re.search(r'Chip type\s*\.{0,12}\s*[:=]?\s*T55x7\b',clean,re.IGNORECASE)
        if chip:
            self._chip_type='T55xx';self.var('chip_type','T55xx')
        state,block=detect_state(clean)
        if scan_mode:
            # Only a valid config with Password set: No proves no search is needed.
            if ok and chip and state=='clear':
                self.protected=False
                return {'status':'clear'}
            # p1detect already established chip presence. A failed config
            # cannot prove a password, so show 'Possibly password protected'.
            # A returned diagnostic is a command response, not a hung reader.
            # Recover only on a silent failure; never reset for a normal warning.
            if not self._p1_verified:
                return {'status':'absent'}
            if not clean.strip() and not self._recover_set_detect():
                return {'status':'detect_failed'}
            self.protected=False
            return {'status':'confirm_locked'}
        # Set Password behaviour remains separate.
        if not ok:
            if self._chip_type and re.search(
                    r'Could not detect modulation|Could not confirm PWD|'
                    r'Cannot detect|No modulation', clean, re.IGNORECASE):
                return {'status':'unknown'}
            return {'status':'detect_failed'}
        if chip and state in ('clear','protected'):
            self.protected=(state=='protected')
            return {'status':state}
        if not self._chip_type:
            return {'status':'absent'}
        return {'status':'unknown'}

    def confirm_scan_warning(self):
        # Proceed only after user intentionally confirms risk.
        if self.mode==3 or not self._chip_type:
            return {'status':'unsafe'}
        # User explicitly accepts risk: P1 detect alone does NOT prove PWD.
        # This branch is for known protected test tags, never automatic.
        if not self._p1_verified:
            return {'status':'unsafe'}
        self.protected=True
        self.reset_budget()
        return {'status':'ok'}

    def confirm_locked_tag(self):
        # Explicit opt-in only: this is NOT automatic proof of PWD.
        # The user must know that this particular test tag is protected.
        if self.mode == 3 or not self._chip_type:
            return {'status':'unsafe'}
        self.protected=True
        self.reset_budget()
        return {'status':'ok'}

    def prepare_date_count(self):
        """Run off the UI thread. Count the exact candidates that will be scanned.

        Freeze the dictionary snapshot between confirmation and scanning, so
        the announced count and the scan use the same candidates even if the
        dictionary file changes in the meantime.
        """
        if self.mode not in (1,2) or not self.start or not self.end:
            return self.error(self.tr('Date range missing'))
        self._prepared_keys=None
        self._prepared_total=None
        keys=[]
        if self.mode==2:
            if not self._inspect_source_dictionary():
                return self.error(self.tr('Dictionary missing'))
            keys=dictionary(DIC)
            if not keys:
                return self.error(self.tr('Dictionary missing'))
        fmt=('YYYYMMDD','DDMMYYYY')[self.date_format_index]
        # Inspect only dictionary entries for overlaps; no list of all dates
        # is allocated, even for a 1900-2100 range.
        duplicates=0
        for key in keys:
            try:
                if fmt=='YYYYMMDD':
                    d=datetime.date(int(key[:4]),int(key[4:6]),int(key[6:8]))
                else:
                    d=datetime.date(int(key[4:8]),int(key[2:4]),int(key[:2]))
            except ValueError:
                continue
            if self.start<=d<=self.end:
                duplicates+=1
        self._prepared_keys=tuple(keys)
        self._prepared_total=len(keys)+(self.end-self.start).days+1-duplicates
        self.var('date_passwords',self._prepared_total)
        return {'status':'ready'}

    def _candidate_generator(self):
        if self.mode in (0,2):
            self._phase='Dictionary'
            for key in (self._prepared_keys if self._prepared_keys is not None else dictionary(DIC)):
                yield key,'Dictionary'
        if self.mode in (1,2):
            for key in dates(self.start,self.end,formats=(('YYYYMMDD','DDMMYYYY')[self.date_format_index],)):yield key,'Date'

    def _next_batch(self):
        if self._pending_batch is not None:
            return list(self._pending_batch)
        keys=[]
        in_batch=set()
        while len(keys)<min(CHK_BATCH_HARD_MAX,self._batch_size):
            try:
                key,phase=next(self._sequence)
            except StopIteration:
                break
            if key in self._seen or key in in_batch:
                # Duplicates must not inflate percentages or be uploaded twice.
                if self._prepared_total is None:
                    self._total=max(self._done, self._total-1)
                continue
            in_batch.add(key)
            keys.append(key)
            self._phase=phase
        if keys:
            self._pending_batch=tuple(keys)
        return keys

    def _commit_batch(self, batch):
        if tuple(batch)!=self._pending_batch:
            raise RuntimeError('Batch state mismatch')
        self._seen.update(batch)
        self._done+=len(batch)
        self._batch_index+=1
        self._pending_batch=None

    def _write_batch(self, keys):
        """Write a client-side dictionary, flush, and re-open it as a sanity check.

        This establishes only Python-side visibility, NOT that PM3 client opened it.
        """
        parent = os.path.dirname(CHK_BATCH)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        tmp = CHK_BATCH + '.new'
        expected = ''.join(str(key).upper() + '\n' for key in keys).encode('ascii')
        try:
            with open(tmp, 'wb') as f:
                f.write(expected)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, CHK_BATCH)
            with open(CHK_BATCH, 'rb') as f:
                actual = f.read()
            file_stat = os.stat(CHK_BATCH)
            ok = (actual == expected and len(actual) == file_stat.st_size)
            parsed = [line.strip().upper() for line in actual.decode('ascii').splitlines() if line.strip()]
            ok = ok and parsed == [str(k).upper() for k in keys]
            if not ok:
                raise IOError('Dictionary readback mismatch')
            return True
        except Exception as e:
            try:
                if os.path.isfile(tmp): os.remove(tmp)
            except OSError:
                pass
            raise

    def _inspect_source_dictionary(self):
        if self.mode not in (0, 2):
            return True
        try:
            if not os.path.isfile(DIC):
                return False
            source_keys=dictionary(DIC)
            st=os.stat(DIC)
            return bool(source_keys)
        except Exception as e:
            return False

    @staticmethod
    def _duration_label(seconds):
        if seconds is None: return 'calculating'
        secs=max(0,int(seconds+0.5))
        if secs >= 3600: return '%dh%02dm'%(secs//3600,(secs%3600)//60)
        if secs >= 60: return '%dm%02ds'%(secs//60,secs%60)
        return '%ds'%secs

    @staticmethod
    def _wall_time():
        return datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    def _log_scan_estimate(self):
        """Predict remaining time using observed fixed ARM baseline + per-key cost.

        The reference values come from the full v29 1000-key test: about
        4m25s expected and 5m upper estimate (5000 -> 22m05s / 25m).
        They are forecasts, not timeout limits or guaranteed maxima.
        """
        if not self._total or self._scan_started_mono is None:
            return
        elapsed_total=max(0.0,monotonic()-self._scan_started_mono)
        remaining=max(0,self._total-self._done)
        if not self._batch_timings or not self._done:
            eta=remaining*0.265
            upper=remaining*0.300
            basis='v29_1000_reference'
            overhead=25.0
            per_key=0.105
            planned=max(1,(remaining+max(1,self._batch_size)-1)//max(1,self._batch_size))
            measured=0.0
        else:
            measured=sum(t['seconds'] for t in self._batch_timings)
            # ARM check has a baseline cost on *every* batch. Do not estimate
            # a short final batch by scaling the whole previous batch time.
            # Smooth per-key times over the last up to four completed batches.
            latest=self._batch_timings[-4:]
            overhead=CHK_ESTIMATED_OVERHEAD
            per_key=max(0.025,sum(max(0.0,t['seconds']-overhead) for t in latest)/max(1,sum(t['keys'] for t in latest)))
            planned=(remaining+max(1,self._batch_size)-1)//max(1,self._batch_size)
            eta=planned*overhead+remaining*per_key
            # Reserve margin for RF variation and verification overhead.
            upper=max(eta*1.12+planned*2.0,eta+planned*5.0)
            basis='completed_batches_with_baseline'
        self._eta_line=self.host.tr('ETA: ~%s')%self._duration_label(eta)
        self._upper_line=self.host.tr('Max est: ~%s')%self._duration_label(upper)

    def _progress(self, percent, label):
        # Do NOT invoke host.set_progress: the built-in progress renderer draws
        # across the system navigation bar on this firmware.  Update only
        # variables for the next UI-thread-rendered content screen.
        pct=max(0,min(100,int(percent)))
        self.var('scan_percent','%d%%'%pct)
        filled=min(20,max(0,int(pct*20/100)))
        self.var('scan_bar',u'\u2588'*filled+u'\u2591'*(20-filled))

    def prepare_batch_ui(self):
        # Runs as call: on the UI thread; NEVER perform RF or flash I/O here.
        total=max(1,self._total)
        pct=min(100,int(100*self._done/total))
        self._progress(pct,'Checked %d / %d'%(self._done,self._total))
        self.var('scan_progress','%d / %d'%(self._done,self._total))
        self.var('scan_phase',self.tr(self._phase or 'Dictionary'))
        self.var('scan_batch',self.host.tr('Batch %d | %d keys')%(self._batch_index+1,min(self._batch_size,max(0,self._total-self._done))))
        self.var('scan_eta',self.tr(self._eta_line))
        self.var('scan_upper',self.tr(self._upper_line))
        return {'status':'ok'}




    def _executor_command(self, command, timeout, phase):
        """One bounded PM3 command, with an isolated output buffer per phase."""
        if self._reader_blocked or self._closed:return -1, 'Reader unavailable'
        import executor
        self._pm3_serial += 1
        seq = self._pm3_serial
        began = monotonic()
        chunks = []
        lock = threading.Lock()
        def on_output(line):
            # Lab401 callbacks may deliver an entire multiline response at once.
            raw = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(line or ''))
            if raw:
                with lock:
                    chunks.append(raw)
        register = getattr(executor, 'add_task_call', None)
        unregister = getattr(executor, 'del_task_call', None)
        registered = False
        try:
            if callable(register) and callable(unregister):
                register(on_output)
                registered = True
            ret = executor.startPM3Task(command, timeout)
            content = executor.getPrintContent() or ''
            with lock:
                captured = '\n'.join(chunks)
            output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(content) + '\n' + captured)
            return ret, output
        finally:
            if registered:
                unregister(on_output)

    def _chk_batch(self):
        """Upload candidate keys to PM3 SPIFFS, then check on the ARM chip.

        A candidate reported by the ARM is NOT a verified password.  The
        client-side confirmation must report 'found valid password' and the
        original Block0 must indicate password protection.
        """
        upload='mem load -f %s -t' % CHK_BATCH
        ret,loaded=self._executor_command(upload, LOAD_TIMEOUT_MS, 'upload')
        m=re.search(r'Wrote\s+(\d+)\s+passwords\s+to file\s+dict_t55xx\.bin', loaded, re.I)
        expected=len(self._pending_batch or ())
        if ret != 1 or m is None or int(m.group(1))!=expected:
            return -2,loaded
        if self.cancel.is_set():
            return -3,loaded
        check='lf t55xx chk -m --r0'
        ret,result=self._executor_command(check,CHK_TIMEOUT_MS,'arm_check')
        return ret,result

    def draw_search_ready(self):
        self._draw_lines(['Ready to search','ARM flash dictionary',self.host.tr('First: %d keys')%CHK_BATCH_INITIAL,'OK - Start search'])

    def do_search(self):
        # One bounded chk -m operation per UI state entry; UI transitions
        # automatically to the next batch, without asking for Continue.
        if not self.protected or not self._p1_verified:
            return {'status':'unsafe'}
        if not self._scan_ready:
            if not self._inspect_source_dictionary():
                return self.error(self.tr('Dictionary missing'))
            if self.mode in (1,2) and (not self.start or not self.end):
                return self.error(self.tr('Date range missing'))
            self._sequence=self._candidate_generator()
            self._seen=set();self._done=0;self._pending_batch=None;self._batch_size=CHK_BATCH_INITIAL;self._batch_index=0;self._last_batch_s=None
            self._scan_started_mono=monotonic();self._scan_started_wall=self._wall_time()
            self._batch_timings=[];self._eta_line='ETA: calculating';self._upper_line='Max est: calculating'
            if self.mode in (1,2):
                if self._prepared_total is None:
                    return self.error(self.tr('Date count missing'))
                self._total=self._prepared_total
            else:
                keys=dictionary(DIC)
                self._total=len(keys)
            self._scan_ready=True
            self._log_scan_estimate()
        if self.cancel.is_set():
            return {'status':'cancel'}
        batch=self._next_batch()
        if not batch:
            return {'status':'none'}
        try:
            self._write_batch(batch)
        except OSError as e:
            return self.error(self.tr('Dictionary temp error'))
        self.var('scan_phase',self._phase)
        self.var('scan_key',batch[-1])
        self.var('scan_progress','%d / %d'%(self._done,self._total))
        batch_wall_start=self._wall_time()
        self._progress(0 if not self._total else int(100*self._done/max(1,self._total)),
                       'Checking %d keys...'%len(batch))
        batch_started=monotonic()
        try:
            ret,out=self._chk_batch()
        except Exception:
            return self._recover_after_failure(self.tr('CHK command error'))
        if ret == -2:
            return self._recover_after_failure(self.tr('SPIFFS upload failed'))
        if ret == -3:
            return {'status':'cancel'}
        if ret == -1:
            return self._recover_after_failure(self.tr('CHK timed out'))
        if ret != 1:
            return self._recover_after_failure(self.tr('CHK command error'))
        output=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',str(out or ''))
        if re.search(r'Loaded\s+\d+\s+passwords from spiffs|found valid password|check pwd failed', output, re.I):
            pass
        else:
            pass
        found=re.search(r'found valid password\s*:?\s*\[\s*([0-9a-fA-F]{8})\s*\]',output,re.I)
        if found:
            key=found.group(1).upper()
            state,block=detect_state(output)
            if key not in batch or state!='protected' or not block or not re.search(r'(?im)^\s*(?:\[=\]\s*)?Password\.+\s*'+re.escape(key)+r'\s*$', output):
                return self._recover_after_failure(self.tr('CHK invalid result'))
            self._pending_batch=None
            self.found=key;self._old_password=key;self._verified_block=block
            self.var('found_password',key)
            return {'status':'found'}
        # chk returns success even when no key is found. Distinguish valid
        # negative results from malformed, interrupted and timed-out replies.
        no_match=bool(re.search(r'check pwd failed|failed to find password',output,re.I)) and bool(re.search(r'time in check pwd',output,re.I))
        if not no_match:
            return self._recover_after_failure(self.tr('CHK incomplete result'))
        self._commit_batch(batch)
        elapsed=max(0.001,monotonic()-batch_started)
        self._last_batch_s=elapsed
        self._batch_timings.append({'keys':len(batch),'seconds':elapsed})
        # Account for the baseline/verification overhead of EACH ARM call.
        # The old keys/elapsed scaling incorrectly shrank batches from 127
        # to ~60, increasing the number of expensive baseline measurements.
        # Keep the same input order and the same memory search algorithm.
        previous_size=self._batch_size
        overhead=min(CHK_ESTIMATED_OVERHEAD,max(0.0,elapsed * 0.70))
        per_key=max(0.025,(elapsed-overhead)/max(1,len(batch)))
        desired=int(max(1.0,(CHK_TARGET_SECONDS-overhead))/per_key)
        # Avoid an aggressive jump from one atypical measurement.
        lower=max(CHK_BATCH_MIN,int(len(batch)*0.75))
        upper=min(CHK_BATCH_MAX,int(len(batch)*1.40)+1)
        target=max(lower,min(upper,desired))
        if elapsed>=CHK_SAFETY_CAP_SECONDS:
            target=min(target,max(CHK_BATCH_MIN,int(len(batch)*0.80)))
        self._batch_size=max(CHK_BATCH_MIN,min(CHK_BATCH_MAX,CHK_BATCH_HARD_MAX,target))
        self._progress(100 if self._done>=self._total else int(100*self._done/max(1,self._total)),
                       'Checked %d / %d'%(self._done,self._total))
        self._log_scan_estimate()
        return {'status':'more'}

    def cancel_scan(self):
        # Cancellation is checked between requests, not during RF transmission.
        self.cancel.set();return {'status':'ok'}

    def save_password(self):
        if not self.found or not KEY.fullmatch(self.found):return self.error(self.tr('Not verified'))
        try:
            os.makedirs(os.path.dirname(DIC),exist_ok=True)
            if self.found not in set(dictionary(DIC)):
                import tempfile
                previous=b''
                if os.path.exists(DIC):
                    with open(DIC,'rb') as source:previous=source.read()
                separator=b'\n' if previous and not previous.endswith(b'\n') else b''
                fd,temp=tempfile.mkstemp(prefix='.t5577-',dir=os.path.dirname(DIC))
                try:
                    with os.fdopen(fd,'wb') as target:
                        target.write(previous+separator+self.found.encode('ascii')+b'\n')
                        target.flush();os.fsync(target.fileno())
                    os.replace(temp,DIC)
                finally:
                    if os.path.exists(temp):os.unlink(temp)
            return {'status':'saved'}
        except OSError:return self.error(self.tr('Dictionary write error'))
    def skip_save(self):
        return {'status':'ok'}

    def _clear_date_warning(self):
        # Keep date validation on its own Canvas layer; do not touch other screens.
        if self.host:
            self.host.getCanvas().delete('_t5577_date_warning')

    def _date_warning(self, message):
        self._clear_date_warning()
        label=self.tr(message)
        from tkinter import font as tkfont
        size=16
        while size>12 and tkfont.Font(root=self.host.getCanvas(),font=resources.get_font(size)).measure(label)>220:
            size-=2
        self.host.getCanvas().create_text(
            120, 75, text=label, anchor='center', font=resources.get_font(size),
            fill='#C62828', tags=('_t5577_date_warning','_jr_content'))
        return {'status':'invalid'}

    def hide_dec(self):
        self._clear_date_warning()
        if self._dec:self._dec.hide();self._dec=None
    def show_dec(self):
        from lib.input_dec import FreeDecInput
        self.hide_dec();label,length=FIELDS[self.field]
        label=(self.tr('Start year:'),self.tr('Start month:'),self.tr('Start day:'),self.tr('End year:'),self.tr('End month:'),self.tr('End day:'))[self.field]
        self._dec=FreeDecInput(self.host.getCanvas(),label=label+' ',max_length=length,font_size=12,
                               hint=self.tr('Up/Down - digit\nLeft/Right - move'),hint_font_size=12)
        # New fields start with 1; left/right still select individual digits.
        self._dec.rollUp()
    def dec_roll_up(self):
        if self._dec:self._clear_date_warning();self._dec.rollUp()
    def dec_roll_down(self):
        if self._dec:self._clear_date_warning();self._dec.rollDown()
    def dec_move_left(self):
        if self._dec:self._clear_date_warning();self._dec.moveLeft()
    def dec_move_right(self):
        if self._dec:self._clear_date_warning();self._dec.moveRight()
    def dec_back(self):self.hide_dec();self.fields=[];self.field=0;return {'status':'back'}
    def dec_capture(self):
        # Validate the complete field, never a transitional digit while editing.
        raw=self._dec.getValue() if self._dec else ''
        if not raw or not raw.isdigit():return self._date_warning(self.tr('Invalid number'))
        n=int(raw);field=self.field
        if field in (0,3) and not 1900<=n<=2100:
            return self._date_warning(self.tr('Year: 1900-2100'))
        if field in (1,4) and not 1<=n<=12:
            return self._date_warning(self.tr('Month: 01-12'))
        if field in (2,5):
            if n<1 or n>31:return self._date_warning(self.tr('Invalid day'))
            try:
                # The year and month were already validated and saved.
                candidate=datetime.date(self.fields[-2],self.fields[-1],n)
            except (ValueError,IndexError):
                return self._date_warning(self.tr('Invalid day'))
            if field==5:
                start=datetime.date(*self.fields[:3])
                if candidate<start:
                    return self._date_warning(self.tr('End before start'))
        self._clear_date_warning()
        self.fields.append(n);self.field+=1
        if self.field<6:return {'status':'more'}
        self.start=datetime.date(*self.fields[:3]);self.end=datetime.date(*self.fields[3:6])
        self.date_start=self.tr('From: ')+self.start.strftime('%d/%m/%Y')
        self.date_end=self.tr('To: ')+self.end.strftime('%d/%m/%Y')
        self.var('date_start',self.date_start);self.var('date_end',self.date_end)
        self.var('date_summary',self.date_start+'\n'+self.date_end)
        if self.mode in (1,2):
            self.date_format_index=0
            return {'status':'format'}
        return {'status':'ready'}

    def hide_hex(self):
        if self._hex:self._hex.hide();self._hex=None
    def show_hex(self):
        from lib.input_hex import FreeHexInput
        self.hide_hex()
        self._hex=FreeHexInput(self.host.getCanvas(),label=self.tr('New password:')+' ',font_size=12,max_length=8,per_line=8,
                               hint=self.tr('8 HEX digits'),hint_font_size=12)
        self._hex.show()
    def hex_roll_up(self):
        if self._hex:self._hex.rollUp()
    def hex_roll_down(self):
        if self._hex:self._hex.rollDown()
    def hex_move_left(self):
        if self._hex:self._hex.moveLeft()
    def hex_move_right(self):
        if self._hex:self._hex.moveRight()
    def hex_back(self):self.hide_hex();return {'status':'back'}
    def hex_capture(self):
        v=(self._hex.getValue() or '').upper() if self._hex else ''
        if not KEY.fullmatch(v):return self.error(self.tr('Exactly 8 HEX digits'))
        self.password=v;self.var('new_password',v)
        return {'status':'change_ready' if self._pending_action=='Change Password' else 'ready'}

    def _write_unconfirmed(self, operation, reason):
        """An interrupted write may already have changed the transponder.

        Never automatically replay it. Even if PM3 recovery succeeds, the
        user must inspect the tag before starting another write operation.
        """
        if not self._recover_set_detect():
            return {'status':'detect_failed'}
        return self.error(self.tr('Write result unknown; check tag'))

    def _check_set_tag_before_write(self):
        """One bounded pre-write guard; distinguish locked/unknown/clear.

        It must not assume that an unresponsive reader means an unlocked tag.
        The tag could have been replaced since the input screen was shown.
        """
        if self.do_p1detect().get('status') != 'ok':
            return 'unknown'
        outcome=self.do_detect().get('status')
        if outcome=='protected':
            return 'protected'
        if outcome=='clear':
            return 'clear'
        return 'unknown'

    def do_set_password(self):
        self.reset_budget()
        if not self.password or not KEY.fullmatch(self.password):
            return self.error(self.tr('Invalid password'))
        # The second check is necessary: the tag could have been swapped
        # between first detection and confirmation. It is bounded to 8 s.
        state=self._check_set_tag_before_write()
        if state=='protected':
            return {'status':'already_locked'}
        if state!='clear':
            return {'status':'unsafe'}
        try:
            ok,out=self.pm3('lf t55xx protect -n '+self.password,30000)
        except Exception as exc:
            return self._write_unconfirmed('Set Password','exception:%s'%type(exc).__name__)
        if not ok:
            return self._write_unconfirmed('Set Password','transport_not_ok')
        if 'Success, tag is locked' not in str(out or ''):
            return self._write_unconfirmed('Set Password','success_marker_missing')
        # Verification is a READ only; never repeat the protect command.
        try:
            verified_ok,detected=self.pm3(
                'lf t55xx detect -p %s -o --r0'%self.password,16000)
            read_ok,readback=self.pm3('lf t55xx read -b 0 -p %s -o --r0'%self.password,12000) if verified_ok else (False,'')
        except Exception as exc:
            return self._write_unconfirmed('Set Password','verify_exception:%s'%type(exc).__name__)
        if not verified_ok or not read_ok or not verified(detected,readback,self.password):
            return self._write_unconfirmed('Set Password','verification_incomplete')
        return {'status':'ok'}

    def do_action(self):
        """Explicitly confirmed operations only; never replay RF writes."""
        self.reset_budget()
        old=self._old_password
        if not old or not KEY.fullmatch(old) or not self._verified_block:
            return self.error(self.tr('Password unverified'))
        try:
            # A changed tag or failed authentication must block the write.
            detect_ok,d=self.pm3('lf t55xx detect -p %s -o --r0'%old,16000)
            if not detect_ok:
                return self._recover_after_failure(self.tr('Tag verification failed'))
            state,block=detect_state(d)
            if state!='protected' or block!=self._verified_block:
                return self.error(self.tr('Tag state changed'))
            read_ok,rd=self.pm3('lf t55xx read -b 0 -p %s -o --r0'%old,12000)
            if not read_ok:
                return self._recover_after_failure(self.tr('PWD verify failed'))
            if not verified(d,rd,old):
                return self.error(self.tr('PWD verify failed'))
            if self._pending_action=='Remove Password':
                clean='%08X'%(int(block,16)&~0x10)
                cmd='lf t55xx write -b 0 -d %s -p %s --r0'%(clean,old)
            elif self._pending_action=='Change Password':
                if not self.password or not KEY.fullmatch(self.password):
                    return self.error(self.tr('Invalid new password'))
                cmd='lf t55xx protect -p %s -n %s --r0'%(old,self.password)
            elif self._pending_action=='Wipe':
                cmd='lf t55xx wipe -p %s --r0'%old
            else:
                return self.error(self.tr('Unknown operation'))
        except Exception:
            return self._recover_after_failure(self.tr('Tag verification failed'))

        operation=self._pending_action
        try:
            write_ok,out=self.pm3(cmd,30000)
        except Exception as exc:
            return self._write_unconfirmed(operation,'exception:%s'%type(exc).__name__)
        if not write_ok:
            return self._write_unconfirmed(operation,'transport_not_ok')
        reply=str(out or '')
        if re.search(r'Write failed|Warning: error writing|Command failed|timeout|unresponsive',reply,re.I):
            return self._write_unconfirmed(operation,'write_error_or_timeout')
        # Never infer success from the write status alone. Verify via RF read.
        try:
            if operation=='Change Password':
                check_ok,v=self.pm3('lf t55xx detect -p %s -o --r0'%self.password,16000)
                state,new_block=detect_state(v)
                read_ok,readback=self.pm3('lf t55xx read -b 0 -p %s -o --r0'%self.password,12000) if check_ok else (False,'')
                success=bool(check_ok and read_ok and new_block==block and verified(v,readback,self.password))
            else:
                check_ok,v=self.pm3('lf t55xx detect --r0',16000)
                state,new_block=detect_state(v)
                success=bool(check_ok and state=='clear' and
                             new_block==('000880E0' if operation=='Wipe' else clean))
                if success and operation=='Wipe':
                    for number in range(1,8):
                        read_ok,readback=self.pm3('lf t55xx read -b %d --r0'%number,12000)
                        if not read_ok or read_block(readback,number)!='00000000':
                            success=False
                            break
        except Exception as exc:
            return self._write_unconfirmed(operation,'verify_exception:%s'%type(exc).__name__)
        if not success:
            return self._write_unconfirmed(operation,'verification_incomplete')
        if operation=='Change Password':
            self._old_password=self.password
        else:
            self._old_password=None
            self._verified_block=None
        return {'status':'ok'}

    def screen_not_protected(self):self.set_screen('not_protected')

    def screen_already_locked(self):self.set_screen('already_locked')

    def screen_unknown(self):self.set_screen('unknown')
    def screen_confirm_locked(self):self.set_screen('confirm_locked')
    def screen_scan_warning(self):self.set_screen('scan_warning')
    def screen_p1_failed(self):self.set_screen('p1_failed')

    def screen_absent(self):self.set_screen('absent')

    def screen_search_failed(self):self.set_screen('search_failed')

    def screen_detect_failed(self):self.set_screen('detect_failed')

    def screen_not_found(self):self.set_screen('not_found')

    def screen_cancelled(self):self.set_screen('cancelled')

    def screen_save_prompt(self):self.set_screen('save_prompt')

    def screen_found_menu(self):self.set_screen('found_menu')

    def screen_date_ready(self):self.set_screen('date_ready')

    def screen_set_confirm(self):self.set_screen('set_confirm')

    def screen_set_success(self):self.set_screen('set_success')

    def screen_error(self):self.set_screen('error')

    def screen_action_confirm(self):self.set_screen("action_confirm")
    def screen_action_success(self):self.set_screen("action_success")
