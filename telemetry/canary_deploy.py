"""Deploy the two reviewed Part 8 plans after a successful receiver gate.

Authorized run: operator requested the Part 8 canary on 2026-09-20.
This command is limited to those fresh plans and refuses repeat deployment.
"""
import json
import subprocess
import sys

from canary_control import EVIDENCE, api, record, run

if __name__ == '__main__':
    name = sys.argv[1]
    assert name in {'CE1', 'DCA-Leaf01'}
    gate = json.loads(subprocess.check_output(['kubectl', 'get', 'job',
        'telemetry-canary-reachability', '-n', 'observability', '-o', 'json']))
    assert gate['status'].get('succeeded') == 1, 'Receiver gate has not passed'
    logs = subprocess.check_output(['kubectl', 'logs', '-n', 'observability',
        'job/telemetry-canary-reachability'], text=True)
    passed = next(json.loads(line) for line in logs.splitlines() if '"passed": true' in line)
    assert len(passed['checks']) == 6
    record('receiver-gate', {'job_uid': gate['metadata']['uid'], 'completed': gate['status']['completionTime'], **passed})
    expected = next(r for r in json.loads((EVIDENCE / 'reviewed-deltas.json').read_text()) if r['name'] == name)
    plans = api('plugins/golden-config/config-plan/?change_control_id=part8-canary-20260920-v2&limit=100')['results']
    matches = [p for p in plans if p['device']['id'] == expected['device'] and p['config_set'].strip() == expected['commands'].strip()]
    assert len(matches) == 1, 'Expected one exact reviewed plan'
    plan = matches[0]
    assert not plan.get('deploy_result'), 'Plan already has a deployment result'
    statuses = api('extras/statuses/?name=Approved&limit=100')['results']
    assert len(statuses) == 1
    api('plugins/golden-config/config-plan/' + plan['id'] + '/', {'status': statuses[0]['id']}, method='PATCH')
    record('approval-' + name, {'device': name, 'plan': plan['id'], 'authorization': 'Operator requested this two-device Part 8 canary on 2026-09-20', 'gate_job': gate['metadata']['uid']})
    run('7c91d376-a0e9-4178-96fe-7b80954ced04', {
        'config_plan': [plan['id']], 'fail_job_on_task_failure': True, 'debug': False}, 'deploy-' + name)
