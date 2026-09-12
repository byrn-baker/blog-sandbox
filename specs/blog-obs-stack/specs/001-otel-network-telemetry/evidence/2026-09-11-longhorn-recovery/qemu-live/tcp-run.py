import subprocess,pathlib,sys,json,shlex,concurrent.futures
root=pathlib.Path('/home/ubuntu/cml-qemu-live');label,src,dst,srcip,dstip,amount,rate,mss=sys.argv[1:]
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
code=(root/'tcp-endpoint.py').read_text()
def launch(host,mode,local,peer):
 cmd=shlex.join(['python3','-c',code,mode,local,peer,'49492',amount,rate,mss]);return subprocess.Popen(ssh+['ubuntu@'+host,cmd],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
server=launch(dst,'server',dstip,srcip);assert server.stdout.readline().strip()=='READY'
client=launch(src,'client',srcip,dstip)
rows=[]
for role,p in [('client',client),('server',server)]:
 out,err=p.communicate(timeout=int(amount)/int(rate)+120)
 r=json.loads(out);r['exit_code']=p.returncode;rows.append(r);print(json.dumps({'label':label,'role':role,**r}),flush=True)
(root/(label+'.json')).write_text(json.dumps(rows,indent=2));assert all(r['ok'] and r['exit_code']==0 for r in rows)
