import subprocess,pathlib,json,time,datetime,threading
r=pathlib.Path('/var/tmp/cml-qemu-canary');stop=threading.Event();samples=[]
nodes={'SPE3':'48f90381-26ee-4d78-a6d9-46896932b9a0','SP1':'5eeb26bb-de28-45cc-999a-2d75d296ca63'}
def monitor():
 while not stop.is_set():
  row={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rings':{}}
  for name,node in nodes.items():
   for nic in ([1,2] if name=='SPE3' else [1,3]):
    p=subprocess.run(['virsh','qemu-monitor-command',node,json.dumps({'execute':'x-query-virtio-queue-status','arguments':{'path':f'/machine/peripheral/net{nic}/virtio-backend','queue':0}})],capture_output=True,text=True)
    try:row['rings'][name+'-net'+str(nic)]=json.loads(p.stdout)['return']
    except Exception:row['rings'][name+'-net'+str(nic)]={'error':p.stderr[-200:]}
  samples.append(row);(r/'traffic-rings.json').write_text(json.dumps(samples));stop.wait(10)
subprocess.run(['ip','netns','exec','canary-b','iperf3','-s','-D','--pidfile',str(r/'iperf-server.pid')],check=True)
thread=threading.Thread(target=monitor,daemon=True);thread.start()
p=subprocess.run(['ip','netns','exec','canary-a','ping','-M','do','-s','8972','-c','5','-W','2','10.0.0.18'],capture_output=True,text=True);(r/'jumbo-ping.txt').write_text(p.stdout);print(json.dumps({'jumbo_ping_status':p.returncode,'output':p.stdout}),flush=True)
rows=[]
try:
 for name,mss,duration,rate in [('small-control',1200,20,'1M'),('jumbo-control',8960,20,'1M'),('jumbo-soak',8960,360,'8M')]:
  cmd=['ip','netns','exec','canary-a','iperf3','-c','10.0.0.18','--bidir','-t',str(duration),'-b',rate,'-M',str(mss),'-l','8960','--pacing-timer','1000','--json','--get-server-output']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=duration+30);(r/(name+'.json')).write_text(p.stdout);(r/(name+'-stderr.txt')).write_text(p.stderr)
  try:
   data=json.loads(p.stdout);row={'name':name,'returncode':p.returncode,'error':data.get('error'),'end':data.get('end'),'start':data.get('start')}
  except Exception:row={'name':name,'returncode':p.returncode,'error':'invalid JSON'}
  rows.append(row);(r/'traffic-summary.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
  if row.get('error') or p.returncode:break
finally:stop.set();thread.join(timeout=15)
print('TRAFFIC_TEST_COMPLETE',flush=True)
