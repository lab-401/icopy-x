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

"""Quick LF Clone plugin -- one-button LF tag clone workflow.

Multi-step flow: scan LF tag -> identify type/ID -> prompt user ->
clone to T55xx blank.  Uses regex patterns from the original
example_lf_clone.py to parse PM3 output.
"""

import re


# Maps LF tag type keywords (from PM3 output) to clone commands.
# The placeholder {id} is replaced with the captured tag ID.
_CLONE_MAP = {
    "EM410x": "lf em 410x clone --id {id}",
    "HID Prox": "lf hid clone -r {id}",
    "Indala": "lf indala clone -r {id}",
    "AWID": "lf awid clone -r {id}",
    "Viking": "lf viking clone --id {id}",
}


def _parse_lf_output(output):
    """Extract (tag_type, tag_id) from ``lf search`` output.

    Returns (None, None) when the output cannot be parsed.
    """
    # EM410x -- look for "EM 410x ID"
    m = re.search(r"EM\s*410x.*?ID[:\s]+([0-9A-Fa-f]{10})", output)
    if m:
        return ("EM410x", m.group(1).upper())

    # HID Prox -- look for "HID Prox Tag ID"
    m = re.search(r"HID Prox.*?ID[:\s]+([0-9A-Fa-f]+)", output, re.IGNORECASE)
    if m:
        return ("HID Prox", m.group(1).upper())

    # Indala
    m = re.search(r"Indala.*?ID[:\s]+([0-9A-Fa-f]+)", output, re.IGNORECASE)
    if m:
        return ("Indala", m.group(1).upper())

    # AWID
    m = re.search(r"AWID.*?ID[:\s]+([0-9A-Fa-f]+)", output, re.IGNORECASE)
    if m:
        return ("AWID", m.group(1).upper())

    # Viking
    m = re.search(r"Viking.*?ID[:\s]+([0-9A-Fa-f]+)", output, re.IGNORECASE)
    if m:
        return ("Viking", m.group(1).upper())

    # Generic fallback -- grab the first [+] line with a hex-like ID
    m = re.search(r"\[\+\].*?:\s*([0-9A-Fa-f]{8,})", output)
    if m:
        return ("Unknown", m.group(1).upper())

    return (None, None)


class QuickLFClonePlugin(object):
    """Entry class for the Quick LF Clone plugin.

    Receives the host (PluginActivity instance) which provides
    pm3_command, set_var, set_progress, show_toast, etc.
    """

    def __init__(self, host=None):
        self.host = host

    def do_scan(self):
        """Called by run:do_scan action.  Runs in a background thread.

        Executes 'lf search' and parses the output to find the tag
        type and ID.  Stores tag_type and tag_id as state variables.

        Returns:
            dict with 'status' key for state machine transitions.
        """
        self.host.set_var('error_msg', '')
        self.host.set_var('tag_type', '')
        self.host.set_var('tag_id', '')

        success, output = self.host.pm3_command('lf search', timeout=10000)

        if not success or not output:
            self.host.set_var('error_msg', 'No tag detected')
            return {'status': 'error'}

        tag_type, tag_id = _parse_lf_output(output)

        if tag_type and tag_id:
            self.host.set_var('tag_type', tag_type)
            self.host.set_var('tag_id', tag_id)
            return {'status': 'found'}
        else:
            self.host.set_var('error_msg', 'Could not identify tag')
            return {'status': 'error'}

    def do_clone(self):
        """Called by run:do_clone action.  Runs in a background thread.

        Looks up the clone command for the identified tag type and
        executes it.  Checks PM3 output for success indicators.

        Returns:
            dict with 'status' key for state machine transitions.
        """
        self.host.set_var('error_msg', '')

        tag_type = self.host.get_var('tag_type', '')
        tag_id = self.host.get_var('tag_id', '')

        if not tag_type or not tag_id:
            self.host.set_var('error_msg', 'No tag data available')
            return {'status': 'error'}

        template = _CLONE_MAP.get(tag_type)
        if template is None:
            self.host.set_var(
                'error_msg',
                'Clone not supported for %s' % tag_type
            )
            return {'status': 'error'}

        cmd = template.format(id=tag_id)

        success, output = self.host.pm3_command(cmd, timeout=15000)

        if not success or not output:
            self.host.set_var('error_msg', 'Clone failed: no response')
            return {'status': 'error'}

        # Check for success indicators in PM3 output
        if '[+]' in output or 'written' in output.lower():
            return {'status': 'done'}

        # Try to extract a specific error message
        error_detail = ''
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('[-]'):
                error_detail = line[4:]
                break

        self.host.set_var(
            'error_msg',
            'Clone failed: %s' % (error_detail or 'unknown error')
        )
        return {'status': 'error'}
