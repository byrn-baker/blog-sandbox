import subprocess,pathlib,json,time,datetime,xml.etree.ElementTree as E
root=pathlib.Path('/var/tmp/cml-qemu-live');root.mkdir(exist_ok=True)
rows=[];nodes={}
for node in subprocess.check_output(['virsh','list','--name'],text=True).split():
 e=E.fromstring(subprocess.check_output(['virsh','dumpxml',node]));nodes[node]=len(e.findall('devices/interface'))
end=time.monotonic()+1800
while time.monotonic()<end and not (root/'stop-sampler').exists():
 row={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rings':{}}
 for node,count in nodes.items():
  for nic in range(count):
   cmd={'execute':'x-query-virtio-queue-status','arguments':{'path':f'/machine/peripheral/net{nic}/virtio-backend','queue':0}}
   p=subprocess.run(['virsh','qemu-monitor-command',node,json.dumps(cmd)],capture_output=True,text=True,timeout=5)
   try:row['rings'][node+':net'+str(nic)]=json.loads(p.stdout)['return']
   except Exception:row['rings'][node+':net'+str(nic)]={'error':'query failed'}
 rows.append(row);(root/'rings.json').write_text(json.dumps(rows));time.sleep(15)
