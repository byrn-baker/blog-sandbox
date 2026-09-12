import subprocess,json
from jobs import root,run,api
code=r'''
import json,re
from nautobot_golden_config.models import GoldenConfig
x=GoldenConfig.objects.get(device__name='DCC-Leaf02')
blocks=re.findall(r'^event-handler lab-gro-off-vmnicet10\n(?:   .*\n)+!\n',x.intended_config+'\n',re.M);assert len(blocks)==1
print(json.dumps({'name':x.device.name,'device_id':str(x.device_id),'commands':blocks[0],'backup_at':str(x.backup_last_success_date),'intended_at':str(x.intended_last_success_date),'backup_handler_count':x.backup_config.count('event-handler lab-gro-off-')}))
'''
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True);assert p.returncode==0
r=json.loads(next(l for l in p.stdout.splitlines() if l.startswith('{')))
assert r['commands']=='event-handler lab-gro-off-vmnicet10\n   action bash sudo -n /sbin/ethtool -K vmnicet10 gro off\n   trigger on-boot\n   delay 60\n!\n'
(root/'recovery-expected.json').write_text(json.dumps(r,indent=2))
run('recovery-plan','82a6fe32-9897-4acc-ba8b-f6d0849d9717',{'device':[r['device_id']],'plan_type':'manual','commands':r['commands'],'change_control_id':'leaf-gro-save-recovery-20260911','debug':False})
plans=api('plugins/golden-config/config-plan/?change_control_id=leaf-gro-save-recovery-20260911&limit=100')['results']
plans=[p for p in plans if p['change_control_id']=='leaf-gro-save-recovery-20260911' and p['device']['id']==r['device_id']];assert len(plans)==1
p=plans[0];assert p['config_set'].strip()==r['commands'].strip() and not p.get('deploy_result')
(root/'recovery-verified.json').write_text(json.dumps([{**r,'plan_id':p['id']}],indent=2));print('Verified recovery plan',p['id'],r['commands'],flush=True)
