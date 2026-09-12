import subprocess,pathlib,selectors,time,os,shlex,json
root=pathlib.Path('/home/ubuntu/gro-rollout/capture-after');root.mkdir(exist_ok=True)
hosts={'dca':'ubuntu@192.168.3.64','dcb':'ubuntu@192.168.3.66','pve':'root@192.168.100.20','eve':'root@192.168.17.2'}
flt='(tcp port 49492 and (host 192.168.100.11 or host 192.168.100.20)) or (udp port 4789 and (udp[50:2] = 49492 or udp[52:2] = 49492))'
procs={};files={};sel=selectors.DefaultSelector();ready=set()
for label,host in hosts.items():
 files[label]=(root/(label+'.pcap')).open('wb');cmd=shlex.join(['sudo','-n','timeout','65','tcpdump','-U','-nn','-B','8192','-s','192','-i','any','-y','LINUX_SLL2','-w','-',flt])
 p=subprocess.Popen(['ssh','-o','BatchMode=yes',host,cmd],stdout=files[label],stderr=subprocess.PIPE);procs[label]=p;sel.register(p.stderr,selectors.EVENT_READ,label)
end=time.monotonic()+15
while len(ready)<4 and time.monotonic()<end:
 for k,_ in sel.select(timeout=1):
  b=os.read(k.fileobj.fileno(),4096).decode(errors='replace')
  if 'listening on' in b:ready.add(k.data)
  if not b:sel.unregister(k.fileobj)
assert len(ready)==4,ready
print('Four packet captures ready',flush=True)
src=pathlib.Path('/home/ubuntu/cml-qemu-live/tcp-endpoint.py').read_text().replace("results={};errors=[]","results={};errors=[];deadline=time.monotonic()+40")
src=src.replace('while sent<amount:',"while sent<amount:\n   if time.monotonic()>deadline:raise TimeoutError('global deadline')")
src=src.replace('while True:',"while True:\n  if time.monotonic()>deadline:raise TimeoutError('global deadline')")
def launch(host,mode,local,peer):
 cmd=shlex.join(['python3','-c',src,mode,local,peer,'49492','262144','125000','1200']);return subprocess.Popen(['ssh','-o','BatchMode=yes',host,cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
sp=launch(hosts['dcb'],'server','192.168.100.20','192.168.100.11');assert sp.stdout.readline().strip()=='READY'
cp=launch(hosts['dca'],'client','192.168.100.11','192.168.100.20')
for label,p in [('client',cp),('server',sp)]:
 try:out,err=p.communicate(timeout=80)
 except subprocess.TimeoutExpired:p.terminate();out,err=p.communicate(timeout=10)
 (root/(label+'.txt')).write_text(out+'\n'+err);print(label,p.returncode,out,flush=True)
for label,p in procs.items():
 p.wait(timeout=80);files[label].close();(root/(label+'-stats.txt')).write_bytes(p.stderr.read())
print('CAPTURES_COMPLETE',flush=True)
