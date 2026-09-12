import subprocess,json,pathlib,datetime
root=pathlib.Path('/tmp/mtu-validation-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));root.mkdir();print(root,flush=True)
code=r'''
import json,concurrent.futures,re,datetime
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
names=list(Device.objects.filter(role__name__in=['Border-Router','CE-Router','P-Router','PE-Router','Route-Reflector','Leaf','Spine']).values_list('name',flat=True))
print(json.dumps({'inventory':sorted(names)}),flush=True)
def run(name):
 d=Device.objects.get(name=name)
 row={'device':name,'ip':str(d.primary_ip4.host),'platform':d.platform.name,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 row['modeled_interfaces']=[{'name':i.name,'mtu':i.mtu,'enabled':i.enabled,'ips':[str(a.address) for a in i.ip_addresses.all()]} for i in d.interfaces.all()]
 try:
  user=d.secrets_group.get_secret_value('Generic','username',obj=d);password=d.secrets_group.get_secret_value('Generic','password',obj=d)
  eos=d.platform.name=='arista_eos'
  with ConnectHandler(device_type='arista_eos' if eos else 'cisco_ios',host=str(d.primary_ip4.host),username=user,password=password,secret=password,conn_timeout=8,auth_timeout=10,banner_timeout=15) as conn:
   if not conn.check_enable_mode():conn.enable()
   commands=['show interfaces','show ip interface brief']
   if not eos:commands+=['show mpls interfaces detail','show ip interface | include ^GigabitEthernet|MTU']
   else:commands+=['show platform tfa counters debug']
   row['commands']={}
   for cmd in commands:
    out=conn.send_command(cmd,read_timeout=25)
    if cmd=='show interfaces':
     # Retain complete interface headers with only MTU and status detail.
     out='\n'.join(l for l in out.splitlines() if re.match(r'^\S.* is ',l) or 'MTU' in l)
    row['commands'][cmd]=out
   row['ok']=not any(re.search(r'% (?:Invalid|Incomplete|Unavailable)',v) for v in row['commands'].values())
 except Exception as e:row.update(ok=False,error=type(e).__name__)
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(run,sorted(names)):print(json.dumps(r),flush=True)
'''
p=subprocess.Popen(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
rows=[]
for l in p.stdout:
 if not l.startswith('{'):continue
 d=json.loads(l)
 if 'inventory' in d:(root/'inventory.json').write_text(json.dumps(d,indent=2));print('Inventory: '+str(len(d['inventory'])),flush=True)
 else:
  rows.append(d);(root/(d['device']+'.json')).write_text(json.dumps(d,indent=2));print(json.dumps({'device':d['device'],'ok':d['ok'],'error':d.get('error')}),flush=True)
p.wait();(root/'summary.json').write_text(json.dumps({'returncode':p.returncode,'devices':[{k:r.get(k) for k in ['device','ok','error']} for r in rows]},indent=2))
if p.returncode:raise RuntimeError('Fleet collector failed')
