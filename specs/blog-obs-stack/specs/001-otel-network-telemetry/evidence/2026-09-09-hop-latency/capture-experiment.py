import subprocess,selectors,time,pathlib,json,datetime,os
root=pathlib.Path('/tmp/lab-latency-20260909/hop-trace-repeat');root.mkdir(exist_ok=True)
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5']
flt='host 192.168.100.11 and host 192.168.100.30 and tcp port 6443 and portrange 48100-48111'
processes={};files={};selector=selectors.DefaultSelector();ready=set()
for label,ip in [('master2','192.168.3.64'),('worker4','192.168.3.69'),('eve','192.168.17.2')]:
 f=open(root/(label+'.txt'),'w');files[label]=f
 capture_filter=flt if label!='eve' else '('+flt+') or (udp port 4789 and ((udp[50:2] >= 48100 and udp[50:2] <= 48111) or (udp[52:2] >= 48100 and udp[52:2] <= 48111)))'
 p=subprocess.Popen(ssh+[('root@' if label=='eve' else 'ubuntu@')+ip,"sudo -n timeout 48 tcpdump -nn -tt -e -vv -S -l -i any -y LINUX_SLL2 '"+capture_filter+"'"],stdout=f,stderr=subprocess.PIPE)
 processes[label]=p;selector.register(p.stderr,selectors.EVENT_READ,label)
end=time.monotonic()+15
while len(ready)<3 and time.monotonic()<end:
 for key,_ in selector.select(timeout=1):
  line=os.read(key.fileobj.fileno(),4096).decode(errors='replace')
  if 'listening on' in line:ready.add(key.data)
  if not line:selector.unregister(key.fileobj)
if len(ready)!=3:
 for p in processes.values():p.terminate()
 for f in files.values():f.close()
 raise RuntimeError('Both captures did not become ready')
code="""import subprocess,json,datetime
for port in range(48100,48112):
 p=subprocess.run(['curl','-k','-sS','--local-port',str(port),'--connect-timeout','2','--max-time','3','-o','/dev/null','-w','%{http_code} %{local_port} %{time_connect} %{time_total}','https://192.168.100.11:6443/livez'],capture_output=True,text=True)
 print(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'port':port,'rc':p.returncode,'timing':p.stdout}),flush=True)
"""
p=subprocess.run(ssh+['ubuntu@192.168.3.69','python3 -'],input=code,capture_output=True,text=True,timeout=42)
(root/'probes.jsonl').write_text(p.stdout)
for label,p in processes.items():
 try:p.wait(timeout=45)
 except subprocess.TimeoutExpired:p.terminate()
 files[label].close()
 (root/(label+'-capture-stats.txt')).write_bytes(p.stderr.read())
print(json.dumps({'captures_ready':sorted(ready),'probes':p.stdout if False else (root/'probes.jsonl').read_text(),'capture_lines':{k:len((root/(k+'.txt')).read_text().splitlines()) for k in processes}}))
