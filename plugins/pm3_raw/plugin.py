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

"""PM3 Raw plugin -- runs 'hw version' and displays the output.

Minimal example showing the plugin API: state machine in ui.json,
background method invoked by run:do_run action.
"""


class PM3RawPlugin(object):
    """Entry class instantiated by PluginActivity.

    Receives the host (PluginActivity instance) which provides
    pm3_command, set_var, show_toast, set_progress, etc.
    """

    def __init__(self, host=None):
        self.host = host

    def do_run(self):
        """Called by run:do_run action.  Runs in a background thread.

        Executes 'hw version' via the PM3 executor and stores the
        output in the {output_lines} variable for ui.json to display.

        Returns:
            dict with 'status' key for state machine transitions.
        """
        self.host.set_var('error_msg', '')
        self.host.set_var('output_lines', '')

        success, output = self.host.pm3_command('hw version', timeout=5000)

        if success and output:
            lines = [l.strip() for l in output.split('\n') if l.strip()]
            # Limit to 8 lines to fit the 240x240 screen
            display = '\n'.join(lines[:8]) if lines else '(empty response)'
            self.host.set_var('output_lines', display)
            return {'status': 'done'}
        else:
            msg = 'PM3 not connected or no response'
            if output:
                msg = output
            self.host.set_var('error_msg', msg)
            return {'status': 'error'}
