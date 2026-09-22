"""Prepare, deploy and verify the approved IOS-XE NetFlow fleet rollout."""
import argparse
import json
from pathlib import Path
import subprocess

import canary_control as control

control.EVIDENCE = Path(__file__).parent / 'evidence' / 'netflow-fleet-20260922'
CHANGE = 'part8-ios-netflow-fleet-20260922'
CANARY = 'CE2'

PLAN_CODE = r'''
import json,re
from datetime import timedelta
from django.utils import timezone
from nautobot_golden_config.models import GoldenConfig

rows=[]
query=GoldenConfig.objects.filter(device__platform__name='cisco_iosxe').exclude(device__name='CE1').select_related('device')
for g in query.order_by('device__name'):
    assert g.intended_last_success_date and g.backup_last_success_date and g.compliance_last_success_date
    assert g.compliance_last_success_date >= max(g.intended_last_success_date,g.backup_last_success_date)
    assert timezone.now()-g.intended_last_success_date < timedelta(minutes=30)
    assert 'flow exporter PART8-EXPORT' not in g.backup_config
    commands=[]
    for block in re.finditer(r'^(flow (?:record|exporter|monitor) PART8-\S+)\n((?:[ \t].*\n)*)',g.intended_config,re.M):
        commands.extend([block[1]]+block[2].rstrip().splitlines()+['exit'])
    interfaces=[]
    for block in re.finditer(r'^interface (\S+)\n((?:[ \t].*\n)*)',g.intended_config,re.M):
        if ' ip flow monitor PART8-MONITOR input' in block[2]:
            assert block[1].startswith('GigabitEthernet') and block[1] != 'GigabitEthernet1'
            assert not re.search(r'^ shutdown$',block[2],re.M)
            interfaces.append(block[1])
            commands.extend(['interface '+block[1],' ip flow monitor PART8-MONITOR input','exit'])
    text='\n'.join(commands)+'\n'
    assert [x for x in ['flow record PART8-IPV4','flow exporter PART8-EXPORT','flow monitor PART8-MONITOR'] if x in text] == [
        'flow record PART8-IPV4','flow exporter PART8-EXPORT','flow monitor PART8-MONITOR']
    assert 'logging ' not in text and 'sflow ' not in text and interfaces
    rows.append({'name':g.device.name,'device':str(g.device.pk),'commands':text,'interfaces':interfaces,
      'intended_at':str(g.intended_last_success_date),'backup_at':str(g.backup_last_success_date),
      'compliance_at':str(g.compliance_last_success_date)})
assert len(rows)==12
print(json.dumps(rows))
'''

VERIFY_CODE = r'''
import concurrent.futures,json,logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
names=NAMES
def collect(d):
    row={'name':d.name,'address':str(d.primary_ip4.host),'commands':{}}
    try:
        user=d.secrets_group.get_secret_value('Generic','username',obj=d)
        password=d.secrets_group.get_secret_value('Generic','password',obj=d)
        with ConnectHandler(device_type='cisco_ios',host=row['address'],username=user,password=password,
          secret=password,session_log=None,conn_timeout=15,auth_timeout=20,banner_timeout=30) as c:
            c.enable()
            for command in ['show flow exporter PART8-EXPORT statistics','show flow monitor PART8-MONITOR statistics',
              'show flow interface','show running-config | section ^flow','show startup-config | section ^flow',
              'show ip bgp summary']:
                row['commands'][command]=c.send_command(command,read_timeout=45)
            row['cli_errors']=[k for k,v in row['commands'].items() if '% Invalid' in v or '% Error' in v]
    except Exception as exc:
        row['error_type']=type(exc).__name__
        row['error']=str(exc).splitlines()[0][:200]
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=min(4,len(names))) as pool:
    rows=list(pool.map(collect,Device.objects.filter(name__in=names).select_related('platform','primary_ip4','secrets_group').order_by('name')))
print(json.dumps(rows))
'''


def shell(code, timeout=180):
    result=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server',
      'shell','--interface','python','--command',code],capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:])
    return json.loads(next(line for line in result.stdout.splitlines() if line.startswith('[')))


def prepare_plans():
    rows=shell(PLAN_CODE)
    control.record('reviewed-deltas',rows)
    for row in rows:
        print(row['name']+': '+', '.join(row['interfaces']),flush=True)
        control.run('82a6fe32-9897-4acc-ba8b-f6d0849d9717',{
          'device':[row['device']],'plan_type':'manual','commands':row['commands'],
          'change_control_id':CHANGE,'debug':False},'plan-'+row['name'])


def selected(names):
    reviewed=json.loads((control.EVIDENCE/'reviewed-deltas.json').read_text())
    expected={row['name']:row for row in reviewed}
    assert names and set(names)<=set(expected)
    plans=control.api('plugins/golden-config/config-plan/?change_control_id='+CHANGE+'&limit=100')['results']
    chosen=[]
    for name in names:
        row=expected[name]
        matches=[p for p in plans if p['device']['id']==row['device'] and p['config_set'].strip()==row['commands'].strip()]
        assert len(matches)==1,name
        assert not matches[0].get('deploy_result'),name+' already deployed'
        chosen.append(matches[0])
    return chosen


def deploy(names,label):
    assert len(names)==1,'Deploy one Config Plan per job; multi-device saves overlap in this dispatcher version'
    service=json.loads(subprocess.check_output(['kubectl','get','endpoints','telemetry-canary','-n','observability','-o','json']))
    ports={p['port'] for subset in service.get('subsets',[]) for p in subset.get('ports',[])}
    assert 2055 in ports,'NetFlow receiver endpoint is absent'
    pods=json.loads(subprocess.check_output(['kubectl','get','pod','-n','observability','-l','app=telemetry-canary','-o','json']))
    assert len(pods['items'])==1 and all(c['ready'] for c in pods['items'][0]['status']['containerStatuses'])
    plans=selected(names)
    approved=control.api('extras/statuses/?name=Approved&limit=100')['results'];assert len(approved)==1
    for plan in plans:
        control.api('plugins/golden-config/config-plan/'+plan['id']+'/',{'status':approved[0]['id']},method='PATCH')
    control.record('approval-'+label,{'devices':names,'plans':[p['id'] for p in plans],
      'authorization':'Operator requested IOS-XE NetFlow fleet deployment on 2026-09-22',
      'receiver_endpoint':sorted(ports)})
    control.run('7c91d376-a0e9-4178-96fe-7b80954ced04',{
      'config_plan':[p['id'] for p in plans],'fail_job_on_task_failure':True,'debug':False},'deploy-'+label)


def verify(names,label):
    rows=shell(VERIFY_CODE.replace('NAMES',repr(names)),300)
    control.record('verify-'+label,rows)
    for row in rows:
        running=row.get('commands',{}).get('show running-config | section ^flow','')
        startup=row.get('commands',{}).get('show startup-config | section ^flow','')
        attached=row.get('commands',{}).get('show flow interface','')
        summary={'name':row['name'],'error_type':row.get('error_type'),'cli_errors':row.get('cli_errors'),
          'running':all(x in running for x in ['flow record PART8-IPV4','flow exporter PART8-EXPORT','flow monitor PART8-MONITOR']),
          'startup':all(x in startup for x in ['flow record PART8-IPV4','flow exporter PART8-EXPORT','flow monitor PART8-MONITOR']),
          'attached':attached.count('monitor:          PART8-MONITOR')}
        print(json.dumps(summary),flush=True)
        assert not summary['error_type'] and not summary['cli_errors'] and summary['running'] and summary['startup'] and summary['attached']>0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['plans','deploy-canary','verify-canary','deploy-wave','verify-wave'])
    parser.add_argument('names',nargs='*')
    args=parser.parse_args()
    if args.action=='plans':prepare_plans()
    elif args.action=='deploy-canary':deploy([CANARY],'canary')
    elif args.action=='verify-canary':verify([CANARY],'canary')
    elif args.action=='deploy-wave':deploy(args.names,'wave-'+args.names[0].lower()+'-'+args.names[-1].lower())
    else:verify(args.names,'wave-'+args.names[0].lower()+'-'+args.names[-1].lower())
