"""Prepare telemetry-only Config Plans from fresh Golden Config output.

Does not deploy. Never selects unrelated interfaces, routing or credentials.
"""
import json
import subprocess

from canary_control import api, record, run

CODE = r'''
import json,re
from nautobot_golden_config.models import GoldenConfig
rows=[]
for g in GoldenConfig.objects.filter(device__name__in=['CE1','DCA-Leaf01']).select_related('device'):
    assert g.intended_last_success_date and g.backup_last_success_date and g.compliance_last_success_date
    assert g.compliance_last_success_date >= g.intended_last_success_date
    assert g.compliance_last_success_date >= g.backup_last_success_date
    before=g.backup_config
    commands=[]
    # First attempt stopped at the protocol field. Permit only that exact
    # unused partial record, then replace it before applying the correction.
    partial=re.search(r'^flow record PART8-IPV4\n((?:[ \t].*\n)*)',before+'\n',re.M)
    if partial:
        assert partial[0].strip() == 'flow record PART8-IPV4\n match ipv4 source address\n match ipv4 destination address'
        commands.append('no flow record PART8-IPV4')
    assert not re.search(r'^(flow (exporter|monitor) PART8-|sflow run|logging.*192\.168\.3\.241)',before,re.M), 'Canary already configured; review instead of redeploying'
    for block in re.finditer(r'^(flow (?:record|exporter|monitor) PART8-\S+)\n((?:[ \t].*\n)*)',g.intended_config,re.M):
        commands.extend([block[1]]+block[2].rstrip().splitlines()+['exit'])
    for line in g.intended_config.splitlines():
        if line.startswith('sflow ') or (line.startswith('logging ') and ('192.168.3.241' in line or 'source-interface' in line or 'trap informational' in line)):
            commands.append(line)
    for block in re.finditer(r'^interface (\S+)\n((?:[ \t].*\n)*)',g.intended_config,re.M):
        if ' ip flow monitor PART8-MONITOR input' in block[2]:
            assert block[1] in ['GigabitEthernet2','GigabitEthernet3','GigabitEthernet4','GigabitEthernet5']
            commands.extend(['interface '+block[1],' ip flow monitor PART8-MONITOR input','exit'])
    assert commands and any('192.168.3.241' in c for c in commands)
    rows.append({'name':g.device.name,'device':str(g.device.pk),'commands':'\n'.join(commands)+'\n','intended_at':str(g.intended_last_success_date),'backup_at':str(g.backup_last_success_date),'compliance_at':str(g.compliance_last_success_date)})
assert len(rows)==2
print(json.dumps(rows))
'''

if __name__ == '__main__':
    result = subprocess.run(['docker', 'exec', 'nautobot_docker_compose-nautobot-1',
        'nautobot-server', 'shell', '--interface', 'python', '--command', CODE],
        capture_output=True, text=True, timeout=60, check=True)
    rows = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('[')))
    record('reviewed-deltas', rows)
    for row in rows:
        print(row['name'] + '\n' + row['commands'], flush=True)
        run('82a6fe32-9897-4acc-ba8b-f6d0849d9717', {
            'device': [row['device']], 'plan_type': 'manual',
            'commands': row['commands'], 'change_control_id': 'part8-canary-20260920-v2',
            'debug': False}, 'plan-' + row['name'])
