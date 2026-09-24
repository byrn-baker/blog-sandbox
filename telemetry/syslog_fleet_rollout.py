"""Operator-approved syslog rollout, 2026-09-24. One device per deployment job."""
import argparse
import json
from pathlib import Path
import subprocess

import canary_control as control
from sflow_fleet_rollout import shell, INTENDED_JOB, BACKUP_JOB, COMPLIANCE_JOB, PLAN_JOB, DEPLOY_JOB

control.EVIDENCE = Path(__file__).parent / 'evidence/syslog-fleet-20260924'
CHANGE = 'part8-syslog-fleet-20260924'
PLATFORMS = {'cisco_iosxe': 13, 'arista_eos': 15}
REQUIRED = {
    'cisco_iosxe': ['logging source-interface GigabitEthernet1 vrf MGMT-VRF',
                    'logging host 192.168.3.241 vrf MGMT-VRF'],
    'arista_eos': ['logging vrf MGMT-VRF host 192.168.3.241',
                   'logging vrf MGMT-VRF source-interface Management1'],
}


def inventory():
    rows = []
    for platform, count in PLATFORMS.items():
        selected = control.api('dcim/devices/?platform=' + platform + '&limit=100')['results']
        assert len(selected) == count, platform
        rows.extend(selected)
    assert len({r['id'] for r in rows}) == 28
    return sorted(rows, key=lambda r: r['name'])


def refresh():
    devices = inventory()
    ids = [r['id'] for r in devices]
    control.record('inventory', [{'name': r['name'], 'id': r['id']} for r in devices])
    for label, job, extra in [
        ('intended', INTENDED_JOB, {}),
        ('backup', BACKUP_JOB, {'commit_message': 'Syslog fleet fresh backups'}),
        ('compliance', COMPLIANCE_JOB, {}),
    ]:
        control.run(job, {'device': ids, 'fail_job_on_task_failure': True, 'debug': False, **extra}, label)


def plans():
    rows = shell('''
import json
from datetime import timedelta
from django.utils import timezone
from nautobot_golden_config.models import GoldenConfig
required = REQUIRED
rows = []
for g in GoldenConfig.objects.filter(device__platform__name__in=list(required)).select_related('device__platform').order_by('device__name'):
    assert g.intended_last_success_date and g.backup_last_success_date and g.compliance_last_success_date
    assert g.compliance_last_success_date >= max(g.intended_last_success_date, g.backup_last_success_date)
    assert timezone.now() - min(g.intended_last_success_date, g.backup_last_success_date) < timedelta(hours=1)
    commands = required[g.device.platform.name]
    assert all(c in g.intended_config.splitlines() for c in commands), g.device.name
    missing = [c for c in commands if c not in g.backup_config.splitlines()]
    rows.append({'name': g.device.name, 'device': str(g.device.pk), 'platform':g.device.platform.name,
                 'commands':'\\n'.join(missing), 'already_configured':not missing,
                 'intended_at':str(g.intended_last_success_date), 'backup_at':str(g.backup_last_success_date)})
assert len(rows) == 28
print(json.dumps(rows))
'''.replace('REQUIRED', repr(REQUIRED)))
    control.record('reviewed-deltas', rows)
    assert {r['name'] for r in rows if r['already_configured']} == {'CE1', 'DCA-Leaf01'}
    for row in rows:
        if row['already_configured']:
            continue
        print(row['name'], row['commands'].splitlines(), flush=True)
        control.run(PLAN_JOB, {'device': [row['device']], 'plan_type':'manual',
                    'commands':row['commands'], 'change_control_id':CHANGE,
                    'debug':False}, 'plan-' + row['name'])


def deploy(name):
    reviewed = json.loads((control.EVIDENCE / 'reviewed-deltas.json').read_text())
    row = next(r for r in reviewed if r['name'] == name)
    assert not row['already_configured']
    plans = control.api('plugins/golden-config/config-plan/?change_control_id=' + CHANGE + '&limit=100')['results']
    matches = [p for p in plans if p['device']['id'] == row['device']
               and p['config_set'].strip() == row['commands'].strip()]
    assert len(matches) == 1 and not matches[0].get('deploy_result'), name
    plan = matches[0]
    endpoint = json.loads(subprocess.check_output(['kubectl','-n','observability','get','endpoints','telemetry-canary','-o','json']))
    assert any(p['port'] == 5514 for s in endpoint.get('subsets',[]) for p in s.get('ports',[]))
    statuses = control.api('extras/statuses/?name=Approved&limit=100')['results']
    assert len(statuses) == 1
    control.api('plugins/golden-config/config-plan/' + plan['id'] + '/',
                {'status':statuses[0]['id']}, method='PATCH')
    control.record('approval-' + name, {'device':name, 'plan':plan['id'],
        'authorization':'Operator requested syslog and SuzieQ fleet rollout on 2026-09-24'})
    control.run(DEPLOY_JOB, {'config_plan':[plan['id']], 'fail_job_on_task_failure':True,
                           'debug':False}, 'deploy-' + name)


def verify(names):
    rows = shell('''
import json, logging
from concurrent.futures import ThreadPoolExecutor
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
def collect(d):
    row = {'name':d.name, 'address':str(d.primary_ip4.host), 'platform':d.platform.name}
    try:
        username = d.secrets_group.get_secret_value('Generic','username',obj=d)
        password = d.secrets_group.get_secret_value('Generic','password',obj=d)
        driver = 'cisco_ios' if d.platform.name == 'cisco_iosxe' else 'arista_eos'
        with ConnectHandler(device_type=driver,host=row['address'],username=username,password=password,
                secret=password,session_log=None,conn_timeout=15,auth_timeout=20,banner_timeout=30) as conn:
            conn.enable()
            row['running'] = conn.send_command('show running-config | include ^logging',read_timeout=45)
            row['startup'] = conn.send_command('show startup-config | include ^logging',read_timeout=45)
            row['status'] = conn.send_command('show logging',read_timeout=45)[0:1600]
    except Exception as e:
        row['error_type'] = type(e).__name__
    return row
devices = list(Device.objects.filter(name__in=NAMES).select_related('primary_ip4','platform','secrets_group'))
assert len(devices) == len(NAMES)
with ThreadPoolExecutor(max_workers=3) as pool:
    rows = list(pool.map(collect,devices))
print(json.dumps(rows))
'''.replace('NAMES', repr(names)), timeout=480)
    control.record('verify-' + ('fleet' if len(names) == 28 else '-'.join(names)), rows)
    for row in rows:
        assert not row.get('error_type'), row['name']
        for field in ['running', 'startup']:
            assert all(c in row[field].splitlines() for c in REQUIRED[row['platform']]), (row['name'], field)
            assert '% Invalid' not in row[field] and '% Error' not in row[field]
        print(json.dumps({'device':row['name'], 'running':True, 'startup':True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['refresh','plans','deploy','verify'])
    parser.add_argument('names', nargs='*')
    args = parser.parse_args()
    if args.action == 'refresh': refresh()
    elif args.action == 'plans': plans()
    elif args.action == 'deploy':
        assert len(args.names) == 1
        deploy(args.names[0])
    else: verify(args.names or [r['name'] for r in inventory()])
