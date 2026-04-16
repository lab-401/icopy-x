##########################################################################
# Required Notice: Copyright ETOILE401 SAS (http://www.lab401.com)
#
# Initial author: ETOILE401 SAS & https://github.com/quantum-x/ as of April 16, 2026
#
# Since this date, each contribution is under the copyright of its respective author.
#
# Copyright of each contribution is tracked by the Git history. See the output of git shortlog -nse for a full list or git log --pretty=short --follow <path/to/sourcefile> |git shortlog -ne to track a specific file.
#
# A mailmap is maintained to map author and committer names and email addresses to canonical names and email addresses.
# If by accident a copyright was removed from a file and is not directly deducible from the Git history, please submit a PR.
#
#
# This software is licensed under the PolyForm Noncommercial License 1.0.0.
# You may not use this software for commercial purposes.
#
# A copy of the license is available at:
# https://polyformproject.org/licenses/noncommercial/1.0.0
#
# This entire header "Required Notice" must remain in place.
##########################################################################

"""Variable resolver — resolves {placeholder} strings from context dicts.

Used by the state machine and renderer to substitute runtime values
(tag UID, scan progress, etc.) into screen definitions loaded from JSON.

Resolution priority: most-recently-pushed context wins.  Unresolved
placeholders remain as-is so downstream code can log / display them.
"""


class VariableResolver:
    """Resolve ``{key}`` placeholders against a stack of context dicts."""

    def __init__(self):
        self._contexts = []  # Stack of dicts, index 0 = oldest

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def push_context(self, ctx: dict):
        """Add a context dict (highest priority)."""
        self._contexts.append(ctx)

    def pop_context(self):
        """Remove most recent context.  Returns the removed dict."""
        if self._contexts:
            return self._contexts.pop()
        return None

    def clear(self):
        """Remove all contexts."""
        self._contexts.clear()

    def set_context(self, ctx: dict):
        """Replace all contexts with a single one."""
        self._contexts = [ctx]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _lookup(self, key: str):
        """Search contexts (newest first) for *key*.

        Supports dotted keys: ``tag.uid`` first looks for the literal
        key ``'tag.uid'``, then for ``ctx['tag']['uid']``.

        Returns ``(True, value)`` on hit, ``(False, None)`` on miss.
        """
        for ctx in reversed(self._contexts):
            # Literal key first
            if key in ctx:
                return True, ctx[key]

            # Dotted traversal
            if '.' in key:
                parts = key.split('.')
                obj = ctx
                try:
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj[part]
                        else:
                            raise KeyError(part)
                    return True, obj
                except (KeyError, TypeError):
                    pass

        return False, None

    def resolve(self, text: str) -> str:
        """Resolve ``{key}`` placeholders in *text*.

        Unresolved placeholders remain as-is: ``{unknown}`` stays ``{unknown}``.
        """
        if not isinstance(text, str) or '{' not in text:
            return text

        result = []
        i = 0
        length = len(text)
        while i < length:
            if text[i] == '{':
                # Find the matching '}'
                end = text.find('}', i + 1)
                if end == -1:
                    # No closing brace — emit rest as-is
                    result.append(text[i:])
                    break
                key = text[i + 1:end]
                found, value = self._lookup(key)
                if found:
                    result.append(str(value))
                else:
                    # Keep unresolved placeholder intact
                    result.append(text[i:end + 1])
                i = end + 1
            else:
                result.append(text[i])
                i += 1

        return ''.join(result)

    def resolve_dict(self, d: dict) -> dict:
        """Recursively resolve all string values in a dict.

        Returns a *new* dict — the original is not mutated.
        """
        out = {}
        for k, v in d.items():
            if isinstance(v, str):
                out[k] = self.resolve(v)
            elif isinstance(v, dict):
                out[k] = self.resolve_dict(v)
            elif isinstance(v, list):
                out[k] = self._resolve_list(v)
            else:
                out[k] = v
        return out

    def _resolve_list(self, lst: list) -> list:
        """Recursively resolve strings inside a list."""
        out = []
        for item in lst:
            if isinstance(item, str):
                out.append(self.resolve(item))
            elif isinstance(item, dict):
                out.append(self.resolve_dict(item))
            elif isinstance(item, list):
                out.append(self._resolve_list(item))
            else:
                out.append(item)
        return out

    # ------------------------------------------------------------------
    # Condition evaluation
    # ------------------------------------------------------------------

    def resolve_condition(self, condition: str, result: dict) -> bool:
        """Evaluate a transition condition string against *result*.

        Supported formats:

        - ``on_result.field==value`` — equality check
        - ``on_result.field!=value`` — inequality check
        - ``on_error`` — True if *result* contains an ``'error'`` key
        - ``on_timeout:ms`` — always False (handled externally)

        Returns True if the condition matches.
        """
        if condition == 'on_error':
            return 'error' in result

        if condition.startswith('on_timeout:'):
            return False

        # Parse on_result.field==value or on_result.field!=value
        if condition.startswith('on_result.'):
            rest = condition[len('on_result.'):]

            # Determine operator
            if '!=' in rest:
                field, expected = rest.split('!=', 1)
                return self._compare_value(result, field, expected, negate=True)
            elif '==' in rest:
                field, expected = rest.split('==', 1)
                return self._compare_value(result, field, expected, negate=False)

        return False

    @staticmethod
    def _compare_value(result: dict, field: str, expected: str, *, negate: bool) -> bool:
        """Compare a field in *result* against an expected string value.

        Boolean strings ``'true'``/``'false'`` are compared case-insensitively
        against Python bools.
        """
        # Navigate dotted field path
        obj = result
        for part in field.split('.'):
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                # Field not found — condition does not match
                return negate  # != matches when field missing, == does not
        actual = obj

        # Coerce expected to match Python types
        expected_lower = expected.lower()
        if expected_lower == 'true':
            match = (actual is True or actual == 'true')
        elif expected_lower == 'false':
            match = (actual is False or actual == 'false')
        elif expected_lower == 'none' or expected_lower == 'null':
            match = (actual is None)
        else:
            # Try numeric comparison, fall back to string
            try:
                match = (actual == int(expected))
            except (ValueError, TypeError):
                try:
                    match = (actual == float(expected))
                except (ValueError, TypeError):
                    match = (str(actual) == expected)

        return (not match) if negate else match
