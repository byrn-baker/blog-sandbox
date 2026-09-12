import subprocess,json,pathlib,sys
mode=sys.argv[1];assert mode in ['apply','restore']
code=r'''
import json,logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
targets=[('DCA-Leaf01','vmnicet5'),('DCB-Leaf01','vmnicet4')];changed=[]
def toggle(name,interface,value,expected):
 d=Device.objects.get(name=name);u=d.secrets_group.get_secret_value('Generic','username',obj=d);p=d.secrets_group.get_secret_value('Generic','password',obj=d)
 with ConnectHandler(device_type='arista_eos',host=str(d.primary_ip4.host),username=u,password=p,secret=p,conn_timeout=15) as c:
  if not c.check_enable_mode():c.enable()
  before=c.send_command('bash ethtool -k '+interface,read_timeout=30);assert 'generic-receive-offload: '+expected+'\n' in before,(name,'unexpected GRO state')
  out=c.send_command('bash sudo ethtool -K '+interface+' gro '+value,read_timeout=30)
  after=c.send_command('bash ethtool -k '+interface,read_timeout=30);assert 'generic-receive-offload: '+value+'\n' in after,(name,'GRO readback failed')
  print(json.dumps({'device':name,'interface':interface,'before':expected,'after':value,'verified':True}),flush=True)
try:
 for name,interface in targets:
  toggle(name,interface,'off' if MODE=='apply' else 'on','on' if MODE=='apply' else 'off');changed.append((name,interface))
except Exception:
 if MODE=='apply':
  for name,interface in reversed(changed):toggle(name,interface,'on','off')
 raise
'''.replace('MODE',repr(mode))
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True)
rows=[json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
pathlib.Path('/home/ubuntu/cml-qemu-live/gro-'+mode+'.json').write_text(json.dumps(rows,indent=2))
for r in rows:print(json.dumps(r))
assert p.returncode==0 and len(rows)==2,'Canary operation failed; inspect per-device state'
