# -*- coding: utf-8 -*-
"""Behavioural tests for PM3/system status-phrase localization.

Workstream: pm3-system-i18n (i18n multi-language, French / fr).

Spec under test:

  * ``src/middleware/pm3_localize.py`` holds the recognized user-facing
    PM3/system phrase set and a ``localize(text)`` function.
  * ``localize`` translates ONLY known human-readable status phrases, via
    ``resources.get_str(phrase)`` where the *English phrase itself* is the
    lookup key.  Translations are supplied by the active language's
    ``system`` category; English falls back to itself.
  * ``localize`` is a STRICT no-op when ``resources.getLanguage() == 'en'``.
  * ``localize`` NEVER alters hex dumps, structured lines, or unknown /
    dynamic output — only whole lines that are a recognized phrase change.
  * The phrase set is seeded with 16 phrases (below) and is trivial to
    extend at runtime.
  * ``src/middleware/executor.py`` calls ``pm3_localize.localize()`` on the
    user-facing result AFTER the ``pm3_compat.translate_response()`` step,
    with a minimal change (an import plus a single call).

Expectations are derived from the spec, not from the current implementation:
each test fails if the behaviour is wrong.  The language files used here are
synthetic and isolated (a temp dir pointed at via the loader's own discovery
hook) so the assertions exercise the mechanism rather than the exact French
wording shipped in data/lang/fr.json.
"""

import inspect
import json
import re

import pytest

import resources
import pm3_localize


# ---------------------------------------------------------------------------
# The 16 phrases the spec says the set must be seeded with (verbatim, ordered).
# ---------------------------------------------------------------------------
SEED_PHRASES = (
    'No card found',
    'No tag found',
    'Card detected',
    'Auth failed',
    'Read failed',
    'Write failed',
    'Unknown card',
    'No valid key',
    'Wrong key',
    'Reading...',
    'Writing...',
    'Scanning...',
    'Done',
    'Success',
    'Failed',
    'Please wait...',
)

# A deterministic, obviously-synthetic translation for a phrase.
def _tr(phrase):
    return '[TL] ' + phrase


def _full_system():
    """A ``system`` category that translates every seed phrase."""
    return {p: _tr(p) for p in SEED_PHRASES}


# ---------------------------------------------------------------------------
# Isolation: never let one test's language / registry / phrase-set mutation
# leak into another.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _restore_state():
    saved_lang = resources._current_language
    saved_registry = resources._LANG_REGISTRY
    saved_phrases = set(pm3_localize._phrases)
    try:
        yield
    finally:
        resources._current_language = saved_lang
        resources._LANG_REGISTRY = saved_registry
        pm3_localize._phrases.clear()
        pm3_localize._phrases.update(saved_phrases)


@pytest.fixture
def use_lang(tmp_path, monkeypatch):
    """install(files, active) -> point the loader at synthetic lang files.

    ``files`` maps a language code to the dict serialised as ``<code>.json``
    in an isolated temp dir.  The loader's own discovery hook is repointed at
    that dir, the in-memory registry is rebuilt through the public reload
    entry point, and the active language is set to *active*.
    """
    def install(files, active):
        lang_dir = tmp_path / 'lang'
        lang_dir.mkdir(exist_ok=True)
        for code, data in files.items():
            (lang_dir / (code + '.json')).write_text(
                json.dumps(data, ensure_ascii=False), encoding='utf-8'
            )
        monkeypatch.setattr(resources, '_find_lang_dir', lambda: str(lang_dir))
        resources.force_check_str_res()
        resources.setLanguage(active)

    return install


def _lang_file(system=None):
    data = {'_name': 'Testish', '_font': 'mononoki'}
    if system is not None:
        data['system'] = system
    return data


# ===========================================================================
# Group A — module surface
# ===========================================================================
class TestModuleSurface:
    def test_localize_is_callable(self):
        assert callable(pm3_localize.localize)

    def test_empty_input_is_returned_unchanged(self, use_lang):
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        assert pm3_localize.localize('') == ''


# ===========================================================================
# Group B — recognized phrases are translated in a non-English language
# ===========================================================================
class TestSeedPhrasesTranslate:
    @pytest.mark.parametrize('phrase', SEED_PHRASES)
    def test_each_seed_phrase_is_translated(self, phrase, use_lang):
        # Active language provides a translation for every seed phrase.
        use_lang({'en': _lang_file({}), 'tl': _lang_file(_full_system())}, 'tl')
        assert pm3_localize.localize(phrase) == _tr(phrase)

    def test_translation_uses_english_phrase_as_the_key(self, use_lang, monkeypatch):
        use_lang({'en': _lang_file({}), 'tl': _lang_file(_full_system())}, 'tl')
        seen = []
        real_get_str = resources.get_str

        def spy(keys):
            seen.append(keys)
            return real_get_str(keys)

        monkeypatch.setattr(resources, 'get_str', spy)
        out = pm3_localize.localize('No card found')
        assert out == _tr('No card found')
        # The English phrase itself is the lookup key handed to get_str.
        assert 'No card found' in seen

    def test_trailing_newline_is_preserved(self, use_lang):
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        assert pm3_localize.localize('Done\n') == _tr('Done') + '\n'

    def test_only_the_phrase_line_changes_in_a_mixed_block(self, use_lang):
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        block = (
            '=== Scan results ===\n'
            'UID: 04 A2 3F 12\n'
            'No card found\n'
            '00 01 02 03 04\n'
        )
        expected = (
            '=== Scan results ===\n'
            'UID: 04 A2 3F 12\n'
            + _tr('No card found') + '\n'
            '00 01 02 03 04\n'
        )
        assert pm3_localize.localize(block) == expected


# ===========================================================================
# Group C — strict no-op for English
# ===========================================================================
class TestEnglishNoop:
    def test_english_returns_text_unchanged(self, use_lang):
        # English active — even recognized phrases are left as-is.  The
        # English file deliberately carries "translations": a strict no-op
        # must NOT apply them, so any non-short-circuiting implementation
        # would corrupt this output.
        use_lang({'en': _lang_file(_full_system())}, 'en')
        text = 'No card found\nDEADBEEF\nDone\n'
        assert pm3_localize.localize(text) == text

    def test_english_is_strict_noop_without_lookups(self, use_lang, monkeypatch):
        # English must short-circuit BEFORE any resources.get_str lookup.
        # The English file carries translations, and get_str is recorded:
        # a correct no-op never calls it and never changes the text.
        use_lang({'en': _lang_file(_full_system())}, 'en')

        calls = []
        real_get_str = resources.get_str

        def spy(keys):
            calls.append(keys)
            return real_get_str(keys)

        monkeypatch.setattr(resources, 'get_str', spy)
        text = 'No card found\nWriting...\n'
        assert pm3_localize.localize(text) == text
        assert calls == []  # no lookups performed for English


# ===========================================================================
# Group D — never alter hex dumps / structured / unknown / dynamic output
# ===========================================================================
class TestNeverAlterNonPhrases:
    def test_hex_dump_is_untouched(self, use_lang):
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        dump = (
            '[00] 04 A2 3F 12 8C 20 11 00  |..?.. ..|\n'
            '[01] FF FF FF FF FF FF 07 80  |........|\n'
            '[02] 00 00 00 00 00 00 00 00  |........|\n'
        )
        assert pm3_localize.localize(dump) == dump

    def test_structured_and_dynamic_lines_are_untouched(self, use_lang):
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        text = (
            'UID: 04 A2 3F 12 8C 20 11\n'
            'ATQA: 00 44\n'
            'Found 3 keys in 1.24s\n'
            '[+] valid key: FFFFFFFFFFFF\n'
        )
        assert pm3_localize.localize(text) == text

    def test_phrase_as_substring_of_a_larger_line_is_not_translated(self, use_lang):
        # "No card found" appears inside a longer structured line; the whole
        # line is not a recognized phrase, so it must be left unchanged.
        use_lang({'tl': _lang_file(_full_system())}, 'tl')
        line = 'Slot 3: No card found during scan\n'
        assert pm3_localize.localize(line) == line

    def test_unrecognized_line_with_a_translation_is_still_not_translated(self, use_lang):
        # The active language happens to carry a translation for a line that
        # is NOT in the recognized phrase set.  localize must gate on the
        # recognized set and leave it unchanged (translate ONLY known phrases).
        mystery = 'Firmware checksum mismatch'
        system = _full_system()
        system[mystery] = '[TL] ' + mystery
        use_lang({'tl': _lang_file(system)}, 'tl')
        assert mystery not in pm3_localize._phrases  # precondition
        assert pm3_localize.localize(mystery) == mystery


# ===========================================================================
# Group E — English falls back to itself for an untranslated known phrase
# ===========================================================================
class TestEnglishFallback:
    def test_untranslated_known_phrase_roundtrips_to_english(self, use_lang):
        # Active language translates most seeds but is MISSING one; the
        # missing one must round-trip unchanged (English), while a present
        # one still translates.
        partial = _full_system()
        del partial['Wrong key']
        use_lang({'en': _lang_file({}), 'tl': _lang_file(partial)}, 'tl')

        assert pm3_localize.localize('Wrong key') == 'Wrong key'
        assert pm3_localize.localize('No card found') == _tr('No card found')


# ===========================================================================
# Group F — the phrase set is trivial to extend
# ===========================================================================
class TestExtendable:
    def test_registering_a_new_phrase_enables_its_translation(self, use_lang):
        new_phrase = 'Battery low'
        use_lang({'tl': _lang_file({new_phrase: '[TL] ' + new_phrase})}, 'tl')

        # Before extension: not recognized, so left unchanged.
        assert pm3_localize.localize(new_phrase) == new_phrase

        # Extend the recognized set at runtime.
        pm3_localize.register_phrases(new_phrase)

        # After extension: recognized and translated.
        assert pm3_localize.localize(new_phrase) == '[TL] ' + new_phrase


# ===========================================================================
# Group G — executor integration (localize after translate_response)
# ===========================================================================
class _FakeSocket:
    """Minimal socket stand-in driving executor._send_and_cache once."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def settimeout(self, _t):
        pass

    def sendall(self, data):
        self.sent.append(data)

    def recv(self, _n):
        if self._chunks:
            return self._chunks.pop(0)
        return b''  # end of stream -> breaks the recv loop


class TestExecutorIntegration:
    def test_executor_imports_pm3_localize_module(self):
        import executor
        assert executor.pm3_localize is pm3_localize

    def test_localize_runs_after_translate_response_on_the_result(self, monkeypatch):
        import executor
        if executor.pm3_compat is None:
            pytest.skip('pm3_compat not available in this environment')

        order = []

        def fake_translate(cmd):
            return cmd  # avoid firmware detection side effects

        def fake_translate_response(text, cmd):
            order.append('translate_response')
            return text + '<TR>'

        def fake_localize(text):
            order.append('localize')
            return text + '<LOC>'

        monkeypatch.setattr(executor.pm3_compat, 'translate', fake_translate)
        monkeypatch.setattr(executor.pm3_compat, 'translate_response', fake_translate_response)
        monkeypatch.setattr(executor.pm3_localize, 'localize', fake_localize)

        fake = _FakeSocket([b'No card found\npm3 -->\n'])
        monkeypatch.setattr(executor, '_socket_instance', fake)
        monkeypatch.setattr(executor, 'LABEL_PM3_CMD_TASK_STOPPING', False)

        result = executor._send_and_cache('hf search')

        # localize is called exactly once, AFTER translate_response.
        assert order == ['translate_response', 'localize']
        # localize received the translate_response output, and its output is
        # what gets returned and cached.
        assert result == 'No card found\n<TR><LOC>'
        assert executor.CONTENT_OUT_IN__TXT_CACHE == result

    def test_executor_change_is_minimal(self):
        import executor
        src = inspect.getsource(executor)
        # An import of the module...
        assert re.search(r'^\s*import\s+pm3_localize\b', src, re.MULTILINE)
        # ...plus exactly one call to localize().
        assert len(re.findall(r'pm3_localize\.localize\s*\(', src)) == 1
