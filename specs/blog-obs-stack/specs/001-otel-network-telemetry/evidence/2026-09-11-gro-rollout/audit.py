import subprocess,json,pathlib
root=pathlib.Path('/home/ubuntu/gro-rollout')
code=r"""
import json,logging,re,concurrent.futures
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
def run(d):
 r={'name':d.name,'id':str(d.pk),'ip':str(d.primary_ip4.host),'modeled':[i.name for i in d.interfaces.all() if re.fullmatch(r'Ethernet[0-9]+',i.name)]}
 try:
  u=d.secrets_group.get_secret_value('Generic','username',obj=d);p=d.secrets_group.get_secret_value('Generic','password',obj=d)
  with ConnectHandler(device_type='arista_eos',host=r['ip'],username=u,password=p,secret=p,conn_timeout=15) as c:
   if not c.check_enable_mode():c.enable()
   r['version']=c.send_command('show version',read_timeout=30)
   r['linux']=c.send_command('bash ip -o link',read_timeout=30)
   r['gro']=c.send_command('bash for i in /sys/class/net/vmnicet*; do n=${i##*/}; echo "$n"; /sbin/ethtool -k "$n" | grep generic-receive-offload; done',read_timeout=30)
   r['handlers']=c.send_command('show running-config | section event-handler',read_timeout=30)
   r['bgp']=c.send_command('show bgp evpn summary',read_timeout=30)
   r['ok']=True
 except Exception as e:r.update(ok=False,error=type(e).__name__)
 return r
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for r in pool.map(run,list(Device.objects.filter(platform__name='arista_eos',name__contains='Leaf'))):print(json.dumps(r),flush=True)
"""
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True)
rows=[json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
(root/'leaf-audit.json').write_text(json.dumps(rows,indent=2))
for r in rows:print(json.dumps({k:r.get(k) for k in ['name','ok','modeled','gro','handlers']}),flush=True)
assert p.returncode==0 and len(rows)==9 and all(r['ok'] for r in rows)
