import subprocess,pathlib,sys,json,shlex,time,concurrent.futures
root=pathlib.Path('/home/ubuntu/gro-rollout');mode=sys.argv[1]
hosts=[('DCA-k3s-m1','192.168.3.63','192.168.100.10'),('DCA-k3s-m2','192.168.3.64','192.168.100.11'),('DCA-k3s-m3','192.168.3.65','192.168.100.12'),('DCB-k3s-w1','192.168.3.66','192.168.100.20'),('DCB-k3s-w2','192.168.3.67','192.168.100.21'),('DCB-k3s-w3','192.168.3.68','192.168.100.22'),('DCC-k3s-w4','192.168.3.69','192.168.100.30'),('DCC-k3s-w5','192.168.3.70','192.168.100.31'),('DCC-k3s-w6','192.168.3.72','192.168.100.32')]
source=pathlib.Path('/home/ubuntu/cml-qemu-live/tcp-endpoint.py').read_text()
def test(a,b,label,amount,rate,mss):
 code=source.replace('results={};errors=[]','results={};errors=[];deadline=time.monotonic()+'+str(amount/rate+45))
 code=code.replace('while sent<amount:',"while sent<amount:\n   if time.monotonic()>deadline:raise TimeoutError('global deadline')")
 code=code.replace('while True:',"while True:\n  if time.monotonic()>deadline:raise TimeoutError('global deadline')")
 def launch(h,role,peer):
  cmd=shlex.join(['timeout',str(int(amount/rate)+80),'python3','-c',code,role,h[2],peer[2],'49492',str(amount),str(rate),str(mss)])
  return subprocess.Popen(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','ubuntu@'+h[1],cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 server=launch(b,'server',a);client=None
 try:
  assert server.stdout.readline().strip()=='READY'
  client=launch(a,'client',b);rows=[]
  for role,p in [('client',client),('server',server)]:
   out,err=p.communicate(timeout=amount/rate+100)
   r=json.loads(out);r.update(exit_code=p.returncode,role=role);rows.append(r)
  result={'label':label,'source':a[0],'destination':b[0],'endpoints':rows}
  (root/(label+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
  assert all(x['ok'] and x['exit_code']==0 for x in rows)
  return result
 finally:
  for p in [client,server]:
   if p and p.poll() is None:p.terminate()
if mode=='small':
 for i,(a,b) in enumerate([(0,3),(1,4),(2,5),(3,6),(4,7),(5,8),(6,0),(7,1),(8,2)]):test(hosts[a],hosts[b],'small-'+str(i),262144,125000,1200)
elif mode=='bounded-soak':
 test(hosts[1],hosts[3],'bounded-soak',8948*2515,125000,8960)
elif mode=='soak':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(test,hosts[a],hosts[b],'soak-'+str(i),8948*10058,500000,8960) for i,(a,b) in enumerate([(1,3),(4,6),(7,0)])]
  for f in futures:f.result()
else:raise ValueError(mode)
