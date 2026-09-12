import subprocess,json,re
from jobs import root,run,api
code=r'''
import json,re
from nautobot_golden_config.models import GoldenConfig
rows=[]
for gc in GoldenConfig.objects.filter(device__platform__name='arista_eos',device__name__contains='Leaf').select_related('device'):
 blocks=re.findall(r'^event-handler lab-gro-off-vmnicet\d+\n(?:   .*\n)+!\n',gc.intended_config+'\n',re.M)
 assert len(blocks)==10,(gc.device.name,len(blocks))
 commands=''.join(blocks)
 expected=''.join('event-handler lab-gro-off-vmnicet'+str(n)+'\n   action bash sudo -n /sbin/ethtool -K vmnicet'+str(n)+' gro off\n   trigger on-boot\n   delay 60\n!\n' for n in range(1,11))
 assert commands==expected,gc.device.name
 assert 'event-handler lab-gro-off-' not in gc.backup_config
 rows.append({'name':gc.device.name,'device_id':str(gc.device.pk),'commands':commands,'intended_at':str(gc.intended_last_success_date),'backup_at':str(gc.backup_last_success_date)})
print(json.dumps(rows))
'''
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True)
assert p.returncode==0,p.stderr[-800:]
rows=json.loads(next(l for l in p.stdout.splitlines() if l.startswith('[')));assert len(rows)==9
(root/'expected-plans.json').write_text(json.dumps(rows,indent=2))
for r in rows:
 run('plan-'+r['name'],'82a6fe32-9897-4acc-ba8b-f6d0849d9717',{'device':[r['device_id']],'plan_type':'manual','commands':r['commands'],'change_control_id':'leaf-gro-20260911','debug':False})
plans=api('plugins/golden-config/config-plan/?change_control_id=leaf-gro-20260911&limit=100')['results']
verified=[]
for r in rows:
 matches=[p for p in plans if p['device']['id']==r['device_id'] and p['change_control_id']=='leaf-gro-20260911']
 assert len(matches)==1,(r['name'],len(matches))
 p=matches[0];assert p['config_set'].strip()==r['commands'].strip() and not p.get('deploy_result')
 verified.append({**r,'plan_id':p['id']})
(root/'verified-plans.json').write_text(json.dumps(verified,indent=2));print('Nine fresh GRO-only plans verified',flush=True)
