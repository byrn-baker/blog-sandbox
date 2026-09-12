"""Prepared diagnostic. Run only after explicit approval for this SP1 Gi6 test."""
from pathlib import Path
import subprocess,json,datetime
s=Path('/tmp/router-cml-state.py').read_text();exec(s.split('for lab in c.all_labs():')[0]);lab=c.join_existing_lab('c11c5f8e-daf2-468c-89d9-dfd626f3b2ff');link=next(l for l in lab.links() if {l.interface_a.node.label,l.interface_b.node.label}=={'BORDER1','SP1'});root=Path('/tmp/border-investigation');root.mkdir(exist_ok=True)
code=r'''
import json,time,logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
connections=[];r={'samples':[]}
def connect(name):
 d=Device.objects.get(name=name);u=d.secrets_group.get_secret_value('Generic','username',obj=d);p=d.secrets_group.get_secret_value('Generic','password',obj=d)
 c=ConnectHandler(device_type='cisco_ios',host=str(d.primary_ip4.host),username=u,password=p,secret=p,conn_timeout=20,auth_timeout=30,banner_timeout=30)
 connections.append(c)
 if not c.check_enable_mode():c.enable()
 return c
try:
 border=connect('BORDER1');peer=connect('SP1')
 before=peer.send_command('show running-config interface GigabitEthernet6',read_timeout=30)
 assert 'mtu 9216' in before and '10.0.0.24' in before and 'isis network point-to-point' in before
 assert 'no isis hello padding' not in before
 r['before']=before
 r['border_before']=border.send_command('show clns traffic',read_timeout=30)
 try:
  r['change']=peer.send_config_set(['interface GigabitEthernet6','no isis hello padding always'],error_pattern=r'% (?:Invalid|Error|Incomplete|Ambiguous)')
  start=time.monotonic()
  for n in range(6):
   time.sleep(10)
   r['samples'].append({'elapsed':round(time.monotonic()-start,2),'border_neighbors':border.send_command('show isis neighbors',read_timeout=20)})
 finally:
  r['restore']=peer.send_config_set(['interface GigabitEthernet6','isis hello padding'],error_pattern=r'% (?:Invalid|Error|Incomplete|Ambiguous)')
  after=peer.send_command('show running-config interface GigabitEthernet6',read_timeout=30)
  r['configuration_restored']=before==after
  r['after']=after
  assert r['configuration_restored'],'SP1 Gi6 configuration differs after rollback'
 r['border_after']=border.send_command('show clns traffic',read_timeout=30)
 r['border_neighbors_after']=border.send_command('show isis neighbors',read_timeout=20)
finally:
 for c in connections:c.disconnect()
 print(json.dumps(r),flush=True)
'''
assert link.capture_status()['starttime'] is None
try:
 link.start_capture(maxpackets=200,maxtime=180,bpfilter='ether[14:2] = 0xfefe')
 result=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],text=True,capture_output=True)
 for line in result.stdout.splitlines():
  if line.startswith('{'):(root/'small-hello-canary.json').write_text(json.dumps(json.loads(line),indent=2))
 response=link._session.get(str(link._session.base_url).rstrip('/')+'/pcap/'+link.id);assert response.status_code==200
 (root/'small-hello-canary.pcap').write_bytes(response.content)
 assert result.returncode==0,'Canary failed; inspect sanitized results and confirm rollback'
 print('Canary completed; rollback verified. Decode capture and compare counters.')
finally:link.stop_capture()
