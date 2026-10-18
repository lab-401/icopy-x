"""Trusted GitHub build identity, exact artifact download and head status helpers.

Never execute this file from a contributor checkout in a privileged workflow.
Only the IPKs downloaded here may cross into the isolated worker.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import zipfile


REPOSITORY = 'lab-401/icopy-x'
CONTEXT = 'QEMU critical flows'


def api(path, payload=None):
    args = ['gh', 'api', 'repos/' + REPOSITORY + '/' + path]
    if payload is not None:
        args += ['--method', 'POST', '--input', '-']
    result = subprocess.run(args, input=json.dumps(payload) if payload is not None else None,
                            capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def validate_run(run, run_id):
    if (run.get('id') != run_id or run.get('repository', {}).get('full_name') != REPOSITORY or
            run.get('path') != '.github/workflows/build-ipk.yml' or run.get('status') != 'completed' or
            run.get('event') not in ('pull_request', 'push', 'workflow_dispatch') or
            not re.fullmatch('[0-9a-f]{40}', run.get('head_sha', ''))):
        raise ValueError('Not a completed build from the expected repository/workflow')
    return run


def current_pulls(run, fetch=api):
    pulls = run['pull_requests']
    # GitHub can omit fork PR associations from workflow_run. Resolve through
    # the commit API; never treat missing association as permission to pass a PR.
    if not pulls and run['event'] == 'pull_request':
        pulls = fetch('commits/' + run['head_sha'] + '/pulls')
    current = []
    for entry in pulls:
        number = entry['number']
        if not isinstance(number, int) or number < 1:
            raise ValueError('Invalid PR number')
        pull = fetch('pulls/' + str(number))
        if (pull['state'] == 'open' and pull['base']['repo']['full_name'] == REPOSITORY and
                pull['base']['ref'] == 'main' and pull['head']['sha'] == run['head_sha']):
            current.append(number)
    if run['event'] == 'pull_request' and not current:
        raise ValueError('Build no longer belongs to a current open PR head')
    return current


def select_artifacts(artifacts, run):
    selected = {}
    for variant in ('flash', 'noflash'):
        matches = [item for item in artifacts if item['name'] == 'icopy-x-' + variant + '-ipk']
        if len(matches) != 1:
            raise ValueError('Expected exactly one artifact for ' + variant)
        item = matches[0]
        identity = item.get('workflow_run', {})
        if (item.get('expired') or not isinstance(item.get('id'), int) or
                not 0 < item['size_in_bytes'] < 64 * 1024**2 or
                identity.get('id') != run['id'] or identity.get('head_sha') != run['head_sha'] or
                identity.get('repository_id') != run['repository']['id']):
            raise ValueError('Artifact identity/availability mismatch')
        selected[variant] = item
    return selected


def extract_ipk(wrapper, output, variant):
    expected = 'icopy-x-' + variant + '.ipk'
    with zipfile.ZipFile(wrapper) as archive:
        entries = archive.infolist()
        if len(entries) != 1:
            raise ValueError('Unexpected artifact wrapper contents')
        entry = entries[0]
        mode = entry.external_attr >> 16
        if (entry.filename != expected or entry.is_dir() or
                stat.S_IFMT(mode) not in (0, stat.S_IFREG) or
                not 0 < entry.file_size < 64 * 1024**2):
            raise ValueError('Unsafe or oversized artifact wrapper')
        data = archive.read(entry)
    (output / expected).write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def identify(run_id):
    run = validate_run(api('actions/runs/' + str(run_id)), run_id)
    pulls = current_pulls(run)
    return run, dict(build_run_id=run_id, build_attempt=run['run_attempt'], head_sha=run['head_sha'],
                     build_url=run['html_url'], event=run['event'], current_pull_requests=pulls,
                     build_conclusion=run['conclusion'])


def publish(run_id, state, url):
    run, _ = identify(run_id)  # recheck the live head before posting any result
    if state == 'success' and run['conclusion'] != 'success':
        raise ValueError('A failed build cannot receive a passing QEMU status')
    if not re.fullmatch(r'https://github\.com/lab-401/icopy-x/actions/runs/[0-9]+', url):
        raise ValueError('Invalid status target URL')
    api('statuses/' + run['head_sha'], dict(state=state, context=CONTEXT, target_url=url,
        description={'pending': 'Testing both IPKs on ARM Python/Tk',
                     'success': 'Both IPKs passed all critical ARM/Tk flows',
                     'failure': 'Build or critical ARM/Tk validation failed'}[state]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('identify', 'download', 'status'))
    parser.add_argument('--run-id', required=True, type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--state', choices=('pending', 'success', 'failure'))
    parser.add_argument('--url')
    args = parser.parse_args()
    if args.run_id < 1:
        parser.error('Invalid build run ID')
    if args.operation == 'status':
        if not args.state or not args.url:
            parser.error('Status needs --state and --url')
        publish(args.run_id, args.state, args.url)
        return
    run, identity = identify(args.run_id)
    if args.operation == 'identify':
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write('head_sha=' + identity['head_sha'] + '\n')
                output.write('build_ok=' + str(run['conclusion'] == 'success').lower() + '\n')
        print(json.dumps(identity, indent=2))
        return
    if run['conclusion'] != 'success' or args.output is None:
        parser.error('Download needs a successful build and a new output directory')
    args.output.mkdir(exist_ok=False)
    artifacts = api('actions/runs/' + str(args.run_id) + '/artifacts?per_page=100')
    if artifacts['total_count'] > 100:
        raise ValueError('Unexpected artifact inventory size')
    selected = select_artifacts(artifacts['artifacts'], run)
    identity['artifacts'] = {}
    for variant, item in selected.items():
        wrapper = args.output / (variant + '.zip')
        with wrapper.open('xb') as stream:
            subprocess.run(['gh', 'api', 'repos/' + REPOSITORY + '/actions/artifacts/' +
                            str(item['id']) + '/zip'], stdout=stream, check=True, timeout=180)
        if wrapper.stat().st_size > 64 * 1024**2:
            raise ValueError('Oversized downloaded artifact')
        digest = extract_ipk(wrapper, args.output, variant)
        wrapper.unlink()
        identity['artifacts'][variant] = dict(id=item['id'], sha256=digest)
    current_pulls(run)  # fail if the PR moved during download
    (args.output / 'build.json').write_text(json.dumps(identity, indent=2) + '\n')


if __name__ == '__main__':
    main()
