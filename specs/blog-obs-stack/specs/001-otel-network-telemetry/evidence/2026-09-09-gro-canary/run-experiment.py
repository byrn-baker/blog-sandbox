import subprocess, json, pathlib, datetime, time, selectors, os, sys
ROOT=pathlib.Path('/tmp/gro-canary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
ROOT.mkdir(); print(json.dumps({'event':'evidence','path':str(ROOT)}),flush=True)
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5']
def cluster(label):
 r=subprocess.run(SSH+['ubuntu@192.168.3.64','sudo -n k3s kubectl --request-timeout=15s get nodes -o json'],capture_output=True,text=True,timeout=25)
 if r.returncode:raise RuntimeError('Cluster query failed')
 data=json.loads(r.stdout); states=[{'name':x['metadata']['name'],'ready':next((c['status'] for c in x['status']['conditions'] if c['type']=='Ready'),None)} for x in data['items']]
 (ROOT/(label+'.json')).write_text(json.dumps(states,indent=2)); print(json.dumps({'event':label,'nodes':states}),flush=True)
 if len(states)!=9 or any(x['ready']!='True' for x in states):raise RuntimeError('Cluster readiness gate failed')
def trace(label,start,count,duration):
 root=ROOT/label;root.mkdir();ps={};fs={};errors={};sel=selectors.DefaultSelector();ready=set()
 last=start+count-1
 flt=f'host 192.168.100.11 and host 192.168.100.30 and tcp port 6443 and portrange {start}-{last}'
 try:
  for name,ip,user in [('master2','192.168.3.64','ubuntu'),('worker4','192.168.3.69','ubuntu'),('eve','192.168.17.2','root')]:
   f=flt if name!='eve' else f'({flt}) or (udp port 4789 and ((udp[50:2] >= {start} and udp[50:2] <= {last}) or (udp[52:2] >= {start} and udp[52:2] <= {last})))'
   fs[name]=open(root/(name+'.txt'),'w');errors[name]=b''
   p=subprocess.Popen(SSH+[user+'@'+ip,f"sudo -n timeout {duration} tcpdump -nn -tt -e -vv -S -l -i any -y LINUX_SLL2 '{f}'"],stdout=fs[name],stderr=subprocess.PIPE)
   ps[name]=p;sel.register(p.stderr,selectors.EVENT_READ,name)
  deadline=time.monotonic()+12
  while len(ready)<3 and time.monotonic()<deadline:
   for key,_ in sel.select(1):
    b=os.read(key.fileobj.fileno(),4096);errors[key.data]+=b
    if b'listening on' in errors[key.data]:ready.add(key.data)
    if not b:sel.unregister(key.fileobj)
  if len(ready)!=3:raise RuntimeError('Capture readiness gate failed')
  print(json.dumps({'event':'captures_ready','phase':label,'collectors':sorted(ready)}),flush=True)
  code="""import subprocess,json,datetime,time
for port in range(START,END):
 r=subprocess.run(['curl','-ksS','--local-port',str(port),'--connect-timeout','2','--max-time','3','-o','/dev/null','-w','%{http_code} %{local_port} %{time_connect} %{time_appconnect} %{time_total}','https://192.168.100.11:6443/livez'],capture_output=True,text=True)
 print(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'port':port,'rc':r.returncode,'timing':r.stdout}),flush=True)
 time.sleep(.15)
""".replace('START',str(start)).replace('END',str(start+count))
  r=subprocess.run(SSH+['ubuntu@192.168.3.69','python3 -'],input=code,capture_output=True,text=True,timeout=count*3.2+8)
  (root/'probes.jsonl').write_text(r.stdout)
  if r.returncode:raise RuntimeError('Probe runner failed')
  rows=[json.loads(l) for l in r.stdout.splitlines()];print(json.dumps({'event':'probes_finished','phase':label,'count':len(rows),'success':sum(x['rc']==0 for x in rows)}),flush=True)
  if len(rows)!=count:raise RuntimeError('Incomplete probe batch')
  for name,p in ps.items():
   p.wait(timeout=duration+5);errors[name]+=p.stderr.read()
   (root/(name+'-capture-stats.txt')).write_bytes(errors[name])
   if p.returncode not in [0,124]:raise RuntimeError('Capture exited unexpectedly')
 finally:
  for p in ps.values():
   if p.poll() is None:p.terminate()
  for f in fs.values():f.close()
  sel.close()
cluster('cluster-before')
worker=r'''
import json,re,datetime,select,sys,time
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
def emit(event,**kw):print(json.dumps({'event':event,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw}),flush=True)
d=Device.objects.get(name='DCA-Leaf01')
assert str(d.primary_ip4.host)=='192.168.3.32'
user=d.secrets_group.get_secret_value('Generic','username',obj=d)
password=d.secrets_group.get_secret_value('Generic','password',obj=d)
unit='lab-gro-canary-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
changed=False
with ConnectHandler(device_type='arista_eos',host=str(d.primary_ip4.host),username=user,password=password,secret=password,conn_timeout=8,auth_timeout=10,banner_timeout=15) as conn:
 if not conn.check_enable_mode():conn.enable()
 def run(cmd,timeout=20):
  out=conn.send_command(cmd,read_timeout=timeout)
  emit('command',command=cmd,output=out)
  if re.search(r'% (?:Invalid|Incomplete|Unavailable)|returned error code|Failed to|Permission denied',out):raise RuntimeError('Device command rejected')
  return out
 def gro():
  out=run('bash sudo -n /sbin/ethtool -k vmnicet5')
  m=re.search(r'^generic-receive-offload: (on|off)',out,re.M)
  if not m:raise RuntimeError('Missing GRO state')
  return m[1]
 try:
  assert 'DCA-Leaf01' in run('show hostname')
  assert run('bash cat /sys/class/net/vmnicet5/address').strip()=='50:00:00:03:00:05'
  assert gro()=='on'
  run('show bgp evpn summary')
  run('bash top -b -n 2 -d 1 | head -18')
  state=run('bash sudo -n systemctl show '+unit+'.timer -p LoadState')
  assert 'LoadState=not-found' in state
  run('bash sudo -n systemd-run --unit='+unit+' --on-active=300s /sbin/ethtool -K vmnicet5 gro on')
  assert run('bash sudo -n systemctl is-active '+unit+'.timer').strip()=='active'
  emit('rollback_armed',unit=unit)
  changed=True
  run('bash sudo -n /sbin/ethtool -K vmnicet5 gro off')
  assert gro()=='off'
  emit('gro_disabled',unit=unit)
  # Parent asks for restoration after captures. The timer survives this process.
  if select.select([sys.stdin],[],[],150)[0]:sys.stdin.readline()
  run('show bgp evpn summary')
  run('bash top -b -n 2 -d 1 | head -18')
 finally:
  if changed:
   run('bash sudo -n /sbin/ethtool -K vmnicet5 gro on')
   assert gro()=='on'
   emit('gro_restored',unit=unit)
   run('bash sudo -n systemctl show '+unit+'.timer -p ActiveState -p NextElapseUSecMonotonic')
'''
p=subprocess.Popen(['docker','exec','-i','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',worker],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
events=[];restored=False
try:
 for line in p.stdout:
  if not line.startswith('{'):continue
  event=json.loads(line);events.append(event)
  if event['event']!='command':print(json.dumps(event),flush=True)
  if event['event']=='gro_disabled':
   try:trace('gro-off',48200,24,92)
   finally:p.stdin.write('RESTORE\n');p.stdin.flush()
  if event['event']=='gro_restored':restored=True
 p.wait(timeout=25)
 if p.returncode or not restored:raise RuntimeError('Canary worker failed or restoration unverified')
finally:
 (ROOT/'device-events.json').write_text(json.dumps(events,indent=2))
 if p.poll() is None:
  try:p.stdin.write('RESTORE\n');p.stdin.flush()
  except Exception:pass
  try:p.wait(timeout=45)
  except subprocess.TimeoutExpired:pass
 (ROOT/'worker-status.json').write_text(json.dumps({'returncode':p.poll(),'restoration_observed':restored}))
cluster('cluster-after')
trace('restored',48300,8,40)
print(json.dumps({'event':'complete','path':str(ROOT),'restored':restored}),flush=True)
