"""Run and record bounded Nautobot canary jobs with existing credentials.

This is an operator tool. Job submission changes lab state. Device selection
is limited to the two approved canaries; deployment still uses Config Plans.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import time
import urllib.request

EVIDENCE = Path(__file__).resolve().parent / "evidence" / "part8-canary"
CANARIES = {"CE1", "DCA-Leaf01"}


def api(path, data=None, method=None):
    settings = json.loads(Path('/home/ubuntu/.kiro/settings/mcp.json').read_text())['mcpServers']['nautobot-mcp']['env']
    def value(key):
        v = os.environ.get(key, settings.get(key, ''))
        return os.environ[v[2:-1]] if v.startswith('${') else v
    req = urllib.request.Request(value('NAUTOBOT_URL').rstrip('/') + '/api/' + path,
        data=None if data is None else json.dumps(data).encode(), method=method,
        headers={'Authorization': 'Token ' + value('NAUTOBOT_TOKEN'), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def record(name, data):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / (name + '.json')).write_text(json.dumps(data, indent=2) + '\n')


def wait(ident):
    for _ in range(300):
        result = api('extras/job-results/' + ident + '/')
        status = result['status']['value']
        if status not in ['PENDING', 'STARTED', 'RECEIVED', 'RETRY']:
            summary = {'id': ident, 'status': status, 'completed': result.get('date_done')}
            record('job-' + ident, summary)
            print(json.dumps(summary), flush=True)
            if status != 'SUCCESS':
                raise RuntimeError('Nautobot job did not succeed: ' + ident)
            return summary
        time.sleep(2)
    raise TimeoutError('Job still running: ' + ident)


def run(job, data, label):
    data['fail_job_on_task_failure'] = True
    data['debug'] = False
    response = api('extras/jobs/' + job + '/run/', {'data': data})
    ident = response['job_result']['id']
    record(label, {'job_result': ident, 'submitted': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'data': data})
    print(label, ident, flush=True)
    return wait(ident)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['sync', 'baseline', 'reservation', 'compliance-setup'])
    args = p.parse_args()
    if args.action == 'sync':
        run('9146523d-0f96-4ad4-b194-ba468afabe7d', {'repository': '6f8a9806-ec63-4e3e-9df3-bab2e757b7ab'}, 'source-sync')
    elif args.action in ['reservation', 'compliance-setup']:
        jobs = api('extras/jobs/?limit=200')['results']
        name = 'Telemetry VIP Reservation' if args.action == 'reservation' else 'Golden Config - Compliance Rules Setup'
        candidates = [j for j in jobs if j['name'] == name and j['enabled']]
        if len(candidates) != 1:
            raise ValueError('Expected one enabled job: ' + name)
        run(candidates[0]['id'], {'dry_run': False}, args.action)
    else:
        devices = [d for d in api('dcim/devices/?limit=100')['results'] if d['name'] in CANARIES]
        if {d['name'] for d in devices} != CANARIES:
            raise ValueError('Canary inventory mismatch')
        ids = [d['id'] for d in devices]
        record('inventory', [{'name': d['name'], 'id': d['id'], 'address': d['primary_ip4']['address']} for d in devices])
        for name, job, extra in [
            ('intended', 'ab420817-1d1f-4d56-a319-382be6970919', {}),
            ('backup', 'f2033b99-24cd-4949-be4e-ed79d8178850', {'commit_message': 'Part 8 canary fresh backups'}),
            ('compliance', '6ffd11a2-7e95-4b93-b900-e134eaee1d4d', {}),
        ]:
            run(job, {'device': ids, **extra}, name)
