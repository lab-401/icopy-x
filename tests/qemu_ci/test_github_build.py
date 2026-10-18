import copy
import importlib.util
import io
from pathlib import Path
import zipfile

import pytest


spec = importlib.util.spec_from_file_location('github_build', Path(__file__).resolve().parents[2] / 'tools/qemu_ci/github_build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


@pytest.fixture
def run():
    return dict(id=12, repository=dict(id=7, full_name=build.REPOSITORY),
                path='.github/workflows/build-ipk.yml', status='completed',
                event='pull_request', head_sha='a' * 40, pull_requests=[dict(number=55)])


@pytest.mark.parametrize('change', [dict(id=13), dict(path='.github/workflows/other.yml'),
    dict(status='in_progress'), dict(event='issue_comment'), dict(head_sha='main'),
    dict(repository=dict(full_name='someone/else'))])
def test_wrong_build_identity_rejected(run, change):
    run.update(change)
    with pytest.raises(ValueError):
        build.validate_run(run, 12)


def test_current_head_required_and_missing_fork_association_resolved(run):
    pull = dict(number=55, state='open', base=dict(ref='main', repo=dict(full_name=build.REPOSITORY)),
                head=dict(sha=run['head_sha']))
    run['pull_requests'] = []
    def fetch(path):
        return [pull] if path.startswith('commits/') else pull
    assert build.current_pulls(run, fetch) == [55]
    pull['head']['sha'] = 'b' * 40
    with pytest.raises(ValueError, match='current open PR head'):
        build.current_pulls(run, fetch)


@pytest.fixture
def artifacts(run):
    return [dict(id=index, name='icopy-x-' + variant + '-ipk', expired=False, size_in_bytes=100,
                 workflow_run=dict(id=12, head_sha=run['head_sha'], repository_id=7))
            for index, variant in enumerate(('flash', 'noflash'), start=1)]


def test_both_unique_exact_artifacts_required(run, artifacts):
    assert set(build.select_artifacts(artifacts, run)) == {'flash', 'noflash'}
    for bad in (artifacts[:1], artifacts + artifacts[:1]):
        with pytest.raises(ValueError):
            build.select_artifacts(bad, run)


@pytest.mark.parametrize('change', [dict(expired=True), dict(size_in_bytes=0),
    dict(size_in_bytes=80 * 1024**2), dict(workflow_run=dict(id=13)),
    dict(workflow_run=dict(id=12, head_sha='b' * 40, repository_id=7)),
    dict(workflow_run=dict(id=12, head_sha='a' * 40, repository_id=8))])
def test_invalid_artifacts_rejected(run, artifacts, change):
    bad = copy.deepcopy(artifacts)
    bad[0].update(change)
    with pytest.raises(ValueError):
        build.select_artifacts(bad, run)


@pytest.mark.parametrize('name', ['../icopy-x-flash.ipk', 'dir/icopy-x-flash.ipk',
                                  'icopy-x-noflash.ipk', '/icopy-x-flash.ipk'])
def test_wrapper_path_is_not_extracted(tmp_path, name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(name, b'package')
    stream.seek(0)
    with pytest.raises(ValueError):
        build.extract_ipk(stream, tmp_path, 'flash')
    assert list(tmp_path.iterdir()) == []


def test_valid_wrapper_only_writes_named_package(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('icopy-x-flash.ipk', b'package')
    stream.seek(0)
    assert len(build.extract_ipk(stream, tmp_path, 'flash')) == 64
    assert (tmp_path / 'icopy-x-flash.ipk').read_bytes() == b'package'
