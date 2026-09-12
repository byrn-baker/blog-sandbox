import subprocess,json,pathlib,datetime,sys
root=pathlib.Path('/home/ubuntu/gro-rollout/fabric');root.mkdir(exist_ok=True)
code=r'''
import json,concurrent.futures,re,datetime,logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
def run(d):
 row={'name':d.name,'id':str(d.pk),'ip':str(d.primary_ip4.host),'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':{}}
 try:
  u=d.secrets_group.get_secret_value('Generic','username',obj=d);p=d.secrets_group.get_secret_value('Generic','password',obj=d)
  with ConnectHandler(device_type='arista_eos' if d.platform.name=='arista_eos' else 'cisco_ios',host=row['ip'],username=u,password=p,secret=p,conn_timeout=15,auth_timeout=20,banner_timeout=30) as c:
   if not c.check_enable_mode():c.enable()
   for cmd in (['show interfaces | include line protocol|MTU','show ip bgp summary','show bgp evpn summary'] if d.platform.name=='arista_eos' else ['show interfaces | include line protocol|MTU','show isis neighbors','show ip bgp summary','show ip bgp vpnv4 all summary']):
    row['commands'][cmd]=c.send_command(cmd,read_timeout=40)
   row['ok']=True
 except Exception as e:
  row['ok']=False;row['error']=type(e).__name__;row['signals']=[s for s in ['Authentication','timed out','Pattern not detected','TCP connection'] if s.lower() in str(e).lower()]
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for r in pool.map(run,list(Device.objects.filter(platform__name__in=['arista_eos','cisco_iosxe']).select_related('platform'))):print(json.dumps(r),flush=True)
'''
code=code.replace('SELECTED',repr(sys.argv[1:]))
p=subprocess.Popen(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
for l in p.stdout:
 if l.startswith('{'):
  r=json.loads(l);(root/(r['name']+'-jumbo-recovery.json')).write_text(json.dumps(r,indent=2));print(json.dumps({'name':r['name'],'ok':r['ok'],'error':r.get('error'),'interfaces':r['commands'].get('show ip interface brief'),'isis':r['commands'].get('show isis neighbors'),'vnic':r['commands'].get('show platform software vnic-if interface-mapping')}),flush=True)
p.wait()
if p.returncode: print('collector exit',p.returncode)
