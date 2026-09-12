import sys,json,subprocess
from jobs import root
names=sys.argv[1:];assert names
code=r'''
import json,logging,re
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
for name in NAMES:
 d=Device.objects.get(name=name);u=d.secrets_group.get_secret_value('Generic','username',obj=d);p=d.secrets_group.get_secret_value('Generic','password',obj=d)
 r={'name':name}
 with ConnectHandler(device_type='arista_eos',host=str(d.primary_ip4.host),username=u,password=p,secret=p,conn_timeout=15) as c:
  if not c.check_enable_mode():c.enable()
  for key,cmd in [('gro','bash for i in /sys/class/net/vmnicet*; do n=${i##*/}; echo "$n"; /sbin/ethtool -k "$n" | grep generic-receive-offload; done'),('running','show running-config | section event-handler'),('startup','show startup-config | section event-handler'),('events','show event-handler'),('bgp','show bgp evpn summary'),('interfaces','show interfaces status')]:
   r[key]=c.send_command(cmd,read_timeout=40)
 r['off_count']=r['gro'].count('generic-receive-offload: off')
 r['handlers_saved']=all('event-handler lab-gro-off-vmnicet'+str(n)+'\n' in r['startup']+'\n' and 'ethtool -K vmnicet'+str(n)+' gro off' in r['startup'] for n in range(1,11))
 r['bgp_established']=len(re.findall(r'\bEstab\b',r['bgp']))
 r['ok']=r['off_count']==10 and r['handlers_saved'] and r['bgp_established']==2
 print(json.dumps(r),flush=True)
'''.replace('NAMES',repr(names))
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True)
rows=[json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
for r in rows:
 (root/(r['name']+'-verified.json')).write_text(json.dumps(r,indent=2));print(json.dumps({k:r[k] for k in ['name','off_count','handlers_saved','ok']}),flush=True)
assert p.returncode==0 and len(rows)==len(names) and all(r['ok'] for r in rows)
