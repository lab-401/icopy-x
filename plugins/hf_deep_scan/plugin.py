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

"""HF Deep Scan plugin -- scans all HF tag types with detailed results.

Runs five PM3 HF commands sequentially, updating the progress bar
after each command and accumulating results for display.
"""


# Commands to execute: (display_name, pm3_command)
_HF_COMMANDS = [
    ("HF Search", "hf search"),
    ("14443A Info", "hf 14a info"),
    ("Ultralight Info", "hf mfu info"),
    ("iCLASS Info", "hf iclass info"),
    ("ISO15693 Info", "hf 15 info"),
]


class HFDeepScanPlugin(object):
    """Entry class for the HF Deep Scan plugin.

    Receives the host (PluginActivity instance) which provides
    pm3_command, set_var, set_progress, show_toast, etc.
    """

    def __init__(self, host=None):
        self.host = host

    def do_scan(self):
        """Called by run:do_scan action.  Runs in a background thread.

        Executes each HF command sequentially, updating progress and
        accumulating result lines.  Extracts [+] and [=] lines from
        PM3 output as the interesting data.

        Returns:
            dict with 'status' key for state machine transitions.
        """
        self.host.set_var('error_msg', '')
        self.host.set_var('scan_results', '')

        total = len(_HF_COMMANDS)
        result_lines = []

        for idx, (name, cmd) in enumerate(_HF_COMMANDS):
            # Update progress: percentage based on command index
            pct = int((idx * 100) / total)
            self.host.set_progress(pct, "Scanning: %s..." % name)

            result_lines.append(">> %s" % name)

            success, output = self.host.pm3_command(cmd, timeout=8000)

            if success and output:
                # Extract key lines: those starting with [+] or [=]
                for line in output.split('\n'):
                    line = line.strip()
                    if line.startswith('[+]') or line.startswith('[=]'):
                        result_lines.append("  %s" % line[4:])
            elif output:
                result_lines.append("  (error: %s)" % output)
            else:
                result_lines.append("  (no response)")

        result_lines.append("")
        result_lines.append("Scan complete")

        # Final progress: 100%
        self.host.set_progress(100, "Done")

        if not result_lines:
            self.host.set_var('error_msg', 'No scan results')
            return {'status': 'error'}

        self.host.set_var('scan_results', '\n'.join(result_lines))
        return {'status': 'done'}
