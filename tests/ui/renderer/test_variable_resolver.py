"""Tests for VariableResolver — placeholder resolution and condition evaluation."""

import pytest

from src.lib._variable_resolver import VariableResolver


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def resolver():
    """Fresh resolver with no contexts."""
    return VariableResolver()


@pytest.fixture
def resolver_with_tag(resolver):
    """Resolver with a typical tag context pushed."""
    resolver.push_context({
        'uid': '04:A2:3B:FF',
        'frequency': '13.56 MHz',
        'tag_family': 'ISO14443A',
        'tag_type_name': 'MIFARE Classic 1K',
        'sak': '08',
        'atqa': '0004',
        'scan_progress': '75',
    })
    return resolver


# ══════════════════════════════════════════════════════════════════════
# Simple {key} resolution
# ══════════════════════════════════════════════════════════════════════

class TestSimpleResolution:

    def test_single_placeholder(self, resolver_with_tag):
        assert resolver_with_tag.resolve('{uid}') == '04:A2:3B:FF'

    def test_placeholder_in_text(self, resolver_with_tag):
        result = resolver_with_tag.resolve('UID: {uid}')
        assert result == 'UID: 04:A2:3B:FF'

    def test_multiple_placeholders(self, resolver_with_tag):
        result = resolver_with_tag.resolve('{sak} / {atqa}')
        assert result == '08 / 0004'

    def test_no_placeholders(self, resolver):
        assert resolver.resolve('Hello World') == 'Hello World'

    def test_empty_string(self, resolver):
        assert resolver.resolve('') == ''

    def test_non_string_passthrough(self, resolver):
        """Non-string input is returned as-is."""
        assert resolver.resolve(42) == 42
        assert resolver.resolve(None) is None

    def test_unclosed_brace(self, resolver):
        """Unclosed brace is emitted as-is."""
        resolver.push_context({'x': '1'})
        assert resolver.resolve('{x') == '{x'


# ══════════════════════════════════════════════════════════════════════
# Missing keys
# ══════════════════════════════════════════════════════════════════════

class TestMissingKeys:

    def test_missing_key_stays(self, resolver):
        """Unresolved placeholders remain as {key}."""
        assert resolver.resolve('{unknown}') == '{unknown}'

    def test_partial_resolution(self, resolver):
        resolver.push_context({'uid': 'AABB'})
        result = resolver.resolve('{uid} / {missing}')
        assert result == 'AABB / {missing}'

    def test_empty_contexts(self, resolver):
        assert resolver.resolve('{anything}') == '{anything}'


# ══════════════════════════════════════════════════════════════════════
# Nested / dotted keys
# ══════════════════════════════════════════════════════════════════════

class TestNestedKeys:

    def test_dotted_key_from_nested_dict(self, resolver):
        resolver.push_context({'tag': {'uid': 'DEAD', 'sak': '08'}})
        assert resolver.resolve('{tag.uid}') == 'DEAD'
        assert resolver.resolve('{tag.sak}') == '08'

    def test_literal_dotted_key_takes_priority(self, resolver):
        """A literal 'tag.uid' key wins over nested traversal."""
        resolver.push_context({
            'tag.uid': 'LITERAL',
            'tag': {'uid': 'NESTED'},
        })
        assert resolver.resolve('{tag.uid}') == 'LITERAL'

    def test_dotted_key_missing_intermediate(self, resolver):
        resolver.push_context({'tag': 'not_a_dict'})
        assert resolver.resolve('{tag.uid}') == '{tag.uid}'

    def test_deep_dotted_key(self, resolver):
        resolver.push_context({'a': {'b': {'c': 'deep'}}})
        assert resolver.resolve('{a.b.c}') == 'deep'


# ══════════════════════════════════════════════════════════════════════
# Context priority
# ══════════════════════════════════════════════════════════════════════

class TestContextPriority:

    def test_most_recent_wins(self, resolver):
        resolver.push_context({'uid': 'OLD'})
        resolver.push_context({'uid': 'NEW'})
        assert resolver.resolve('{uid}') == 'NEW'

    def test_fallback_to_older(self, resolver):
        resolver.push_context({'uid': 'OLD', 'extra': 'from_old'})
        resolver.push_context({'uid': 'NEW'})
        assert resolver.resolve('{extra}') == 'from_old'

    def test_pop_restores_previous(self, resolver):
        resolver.push_context({'uid': 'OLD'})
        resolver.push_context({'uid': 'NEW'})
        assert resolver.resolve('{uid}') == 'NEW'
        resolver.pop_context()
        assert resolver.resolve('{uid}') == 'OLD'

    def test_set_context_replaces_all(self, resolver):
        resolver.push_context({'a': '1'})
        resolver.push_context({'b': '2'})
        resolver.set_context({'c': '3'})
        assert resolver.resolve('{a}') == '{a}'
        assert resolver.resolve('{b}') == '{b}'
        assert resolver.resolve('{c}') == '3'

    def test_clear_removes_all(self, resolver):
        resolver.push_context({'uid': 'X'})
        resolver.clear()
        assert resolver.resolve('{uid}') == '{uid}'

    def test_pop_empty_returns_none(self, resolver):
        assert resolver.pop_context() is None


# ══════════════════════════════════════════════════════════════════════
# resolve_dict
# ══════════════════════════════════════════════════════════════════════

class TestResolveDict:

    def test_flat_dict(self, resolver_with_tag):
        d = {'label': 'UID', 'value': '{uid}'}
        result = resolver_with_tag.resolve_dict(d)
        assert result == {'label': 'UID', 'value': '04:A2:3B:FF'}

    def test_nested_dict(self, resolver_with_tag):
        d = {
            'content': {
                'header': '{tag_family}',
                'subheader': '{tag_type_name}',
            }
        }
        result = resolver_with_tag.resolve_dict(d)
        assert result['content']['header'] == 'ISO14443A'
        assert result['content']['subheader'] == 'MIFARE Classic 1K'

    def test_list_in_dict(self, resolver_with_tag):
        d = {
            'fields': [
                {'label': 'Freq', 'value': '{frequency}'},
                {'label': 'UID', 'value': '{uid}'},
            ]
        }
        result = resolver_with_tag.resolve_dict(d)
        assert result['fields'][0]['value'] == '13.56 MHz'
        assert result['fields'][1]['value'] == '04:A2:3B:FF'

    def test_non_string_values_preserved(self, resolver_with_tag):
        d = {'max': 100, 'enabled': True, 'items': None}
        result = resolver_with_tag.resolve_dict(d)
        assert result == {'max': 100, 'enabled': True, 'items': None}

    def test_original_not_mutated(self, resolver_with_tag):
        d = {'value': '{uid}'}
        result = resolver_with_tag.resolve_dict(d)
        assert d['value'] == '{uid}'
        assert result['value'] == '04:A2:3B:FF'

    def test_nested_list_in_list(self, resolver):
        resolver.push_context({'x': 'resolved'})
        d = {'rows': [['a', '{x}'], ['b', '{x}']]}
        result = resolver.resolve_dict(d)
        assert result['rows'] == [['a', 'resolved'], ['b', 'resolved']]


# ══════════════════════════════════════════════════════════════════════
# Condition evaluation
# ══════════════════════════════════════════════════════════════════════

class TestConditions:

    def test_equality_true(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found==true', {'found': True}
        ) is True

    def test_equality_false(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found==true', {'found': False}
        ) is False

    def test_equality_string_true(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found==true', {'found': 'true'}
        ) is True

    def test_inequality(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found!=true', {'found': False}
        ) is True

    def test_inequality_when_equal(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found!=true', {'found': True}
        ) is False

    def test_on_error_present(self, resolver):
        assert resolver.resolve_condition(
            'on_error', {'error': 'timeout'}
        ) is True

    def test_on_error_absent(self, resolver):
        assert resolver.resolve_condition(
            'on_error', {'found': True}
        ) is False

    def test_on_timeout_always_false(self, resolver):
        assert resolver.resolve_condition(
            'on_timeout:5000', {}
        ) is False

    def test_string_value_comparison(self, resolver):
        assert resolver.resolve_condition(
            'on_result.type==mifare', {'type': 'mifare'}
        ) is True

    def test_string_value_mismatch(self, resolver):
        assert resolver.resolve_condition(
            'on_result.type==mifare', {'type': 'desfire'}
        ) is False

    def test_numeric_comparison(self, resolver):
        assert resolver.resolve_condition(
            'on_result.count==3', {'count': 3}
        ) is True

    def test_missing_field_equality(self, resolver):
        """Missing field means == does not match."""
        assert resolver.resolve_condition(
            'on_result.missing==true', {}
        ) is False

    def test_missing_field_inequality(self, resolver):
        """Missing field means != does match."""
        assert resolver.resolve_condition(
            'on_result.missing!=true', {}
        ) is True

    def test_nested_field_in_result(self, resolver):
        result = {'scan': {'complete': True}}
        assert resolver.resolve_condition(
            'on_result.scan.complete==true', result
        ) is True

    def test_unknown_condition_format(self, resolver):
        assert resolver.resolve_condition(
            'bogus_condition', {'found': True}
        ) is False

    def test_false_string_comparison(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found==false', {'found': False}
        ) is True

    def test_false_string_comparison_with_string_value(self, resolver):
        assert resolver.resolve_condition(
            'on_result.found==false', {'found': 'false'}
        ) is True
