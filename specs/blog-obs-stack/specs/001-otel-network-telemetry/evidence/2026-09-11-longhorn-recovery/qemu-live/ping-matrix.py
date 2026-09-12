import subprocess,json,pathlib,concurrent.futures
hosts={'DCA':('192.168.3.64','192.168.100.11'),'DCB':('192.168.3.66','192.168.100.20'),'DCC':('192.168.3.69','192.168.100.30')}
def run(pair):
 src,dst=pair;p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','ubuntu@'+hosts[src][0],'ping','-M','do','-s','8972','-c','5','-W','2',hosts[dst][1]],capture_output=True,text=True,timeout=25)
 return {'source':src,'destination':dst,'ip_packet_bytes':9000,'ok':p.returncode==0,'output':p.stdout,'error':p.stderr}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,[(s,d) for s in hosts for d in hosts if s!=d]))
pathlib.Path('/home/ubuntu/cml-qemu-live/jumbo-ping-matrix.json').write_text(json.dumps(rows,indent=2))
for r in rows:print(json.dumps(r),flush=True)
assert all(r['ok'] for r in rows)
