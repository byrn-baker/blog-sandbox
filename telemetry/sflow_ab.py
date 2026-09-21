"""Approved DCA-Leaf01 sFlow off/on comparison, September 21, 2026.

Source changes must be validated, committed, pushed and synced separately.
Deployment accepts only one exact run-state command from fresh intent.
"""
import argparse
import json
import shlex
import subprocess
from pathlib import Path

import canary_control as control
import diagnose_udp as udp
from diagnose_leaf import CODE as READ_CODE

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence' / 'sflow-ab-20260921'
control.EVIDENCE = udp.EVIDENCE = EVIDENCE


def django(code):
    p = subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1',
        'nautobot-server','shell','--interface','python','--command',code],
        capture_output=True,text=True,check=True,timeout=180)
    return json.loads(next(x for x in p.stdout.splitlines() if x.startswith('{')))


def device():
    rows = control.api('dcim/devices/?name=DCA-Leaf01')['results']
    assert len(rows) == 1 and rows[0]['name'] == 'DCA-Leaf01'
    return rows[0]['id']


def baseline(label):
    for name, job in [('intended','ab420817-1d1f-4d56-a319-382be6970919'),
                      ('backup','f2033b99-24cd-4949-be4e-ed79d8178850'),
                      ('compliance','6ffd11a2-7e95-4b93-b900-e134eaee1d4d')]:
        control.run(job, {'device':[device()], 'fail_job_on_task_failure':True,
                         'debug':False}, label+'-'+name)


def deploy(state):
    command = 'no sflow run' if state == 'off' else 'sflow run'
    code = r'''
import json,re
from django.utils import timezone
from nautobot_golden_config.models import GoldenConfig
g=GoldenConfig.objects.get(device__name='DCA-Leaf01')
assert all([g.intended_last_success_date,g.backup_last_success_date,g.compliance_last_success_date])
assert g.compliance_last_success_date >= max(g.intended_last_success_date,g.backup_last_success_date)
assert (timezone.now()-g.intended_last_success_date).total_seconds()<900
print(json.dumps({'intended_sflow':[x for x in g.intended_config.splitlines() if x.startswith(('sflow ','no sflow '))],
 'backup_sflow':[x for x in g.backup_config.splitlines() if x.startswith(('sflow ','no sflow '))],
 'intended_at':str(g.intended_last_success_date),'backup_at':str(g.backup_last_success_date)}))
'''
    state_read = django(code)
    assert command in state_read['intended_sflow'], 'Intent does not authorize this command'
    assert ('sflow run' in state_read['backup_sflow']) == (state == 'off'), 'Unexpected current state'
    control.record(state+'-review',dict(command=command,**state_read))
    change = 'part8-sflow-ab-20260921-'+state
    control.run('82a6fe32-9897-4acc-ba8b-f6d0849d9717',
        {'device':[device()],'plan_type':'manual','commands':command+'\n',
         'change_control_id':change,'debug':False},state+'-plan')
    plans=control.api('plugins/golden-config/config-plan/?change_control_id='+change)['results']
    assert len(plans)==1 and plans[0]['config_set'].strip()==command
    plan=plans[0]
    assert plan['device']['id']==device() and not plan.get('deploy_result')
    approved=control.api('extras/statuses/?name=Approved')['results']
    assert len(approved)==1
    control.api('plugins/golden-config/config-plan/'+plan['id']+'/',
                {'status':approved[0]['id']},method='PATCH')
    control.record(state+'-approval',{'device':'DCA-Leaf01','plan':plan['id'],
        'command':command,'authorization':'User approved sFlow-off comparison followed by restoration on 2026-09-21'})
    control.run('7c91d376-a0e9-4178-96fe-7b80954ced04',
        {'config_plan':[plan['id']],'fail_job_on_task_failure':True,'debug':False},state+'-deploy')
    verify(state)


def verify(state):
    cmds=['show sflow','show running-config | section sflow','show startup-config | section sflow',
          'show interfaces counters discards','show platform tfa counters kernel interfaces',
          'bash sudo -n ss -0 -a -m -p -n -O']
    start=READ_CODE.index(' cmds=');end=READ_CODE.index('\n print(json.dumps',start)
    result=django(READ_CODE[:start]+' cmds='+repr(cmds)+READ_CODE[end:])
    enabled='Enabled: yes' in result['commands']['show sflow']
    running='Running: yes' in result['commands']['show sflow']
    assert enabled == running == (state=='on'), 'Operational sFlow state mismatch'
    for cmd in cmds[1:3]:
        assert ('sflow run' in result['commands'][cmd].splitlines()) == (state=='on'), 'Saved state mismatch'
    control.record(state+'-verified',result)
    print(json.dumps({'verified':state,'at':result['at']}),flush=True)


def observe(label):
    # Live bridge ownership is captured before the probes. No bridge changes.
    for suffix,cmd in [('links','ip -j link'),('bridges','bridge -j link'),
                       ('qdiscs','tc -s qdisc show')]:
        out=subprocess.check_output(['ssh','-o','BatchMode=yes','root@192.168.17.2',cmd],text=True)
        udp.save(label+'-eve-'+suffix,json.loads(out) if suffix!='qdiscs' else {'output':out})
    sample="""import subprocess,time,json
for i in range(125):
 out=subprocess.check_output(['ss','-0','-a','-m','-p','-n','-O'],text=True)
 print(json.dumps({'time':time.time(),'sockets':[' '.join(x.split()) for x in out.splitlines() if any(':'+n+' ' in x for n in ['vmnicet1','vmnicet2','vmnicet5'])]}),flush=True)
 time.sleep(.25)
"""
    start=READ_CODE.index(' cmds=');end=READ_CODE.index('\n print(json.dumps',start)
    cmd='bash sudo -n python3 -c '+shlex.quote('exec('+repr(sample)+')')
    code=READ_CODE[:start]+' print("READY",flush=True)\n cmds='+repr([cmd])+READ_CODE[end:]
    code=code.replace('read_timeout=30','read_timeout=80')
    monitor=subprocess.Popen(['docker','exec','nautobot_docker_compose-nautobot-1',
        'nautobot-server','shell','--interface','python','--command',code],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    for line in monitor.stdout:
        if line.strip()=='READY':break
    else: raise RuntimeError('Socket monitor failed before probe')
    udp.captured_run(True,'-'+label+'-1')
    output,errors=monitor.communicate(timeout=90)
    assert monitor.returncode==0, 'Socket monitor failed'
    result=json.loads(next(x for x in output.splitlines() if x.startswith('{')))
    samples=[json.loads(x) for x in next(iter(result['commands'].values())).splitlines() if x.startswith('{')]
    assert samples
    udp.save(label+'-socket-monitor',samples)
    udp.captured_run(True,'-'+label+'-2')
    print('Completed observations '+label,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['baseline','deploy','verify','observe'])
    p.add_argument('label')
    args=p.parse_args()
    if args.action in ['deploy','verify']:assert args.label in ['on','off']
    globals()[args.action](args.label)
