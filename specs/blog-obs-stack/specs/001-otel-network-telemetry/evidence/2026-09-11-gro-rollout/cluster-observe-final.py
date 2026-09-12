import subprocess,json,pathlib,time,datetime
root=pathlib.Path('/home/ubuntu/gro-rollout')
code=r'''
import subprocess,json,datetime
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def get(kind,namespace=None):
 args=['sudo','-n','k3s','kubectl','--request-timeout=20s','get',kind,'-o','json']
 args+=['-n',namespace] if namespace else ['-A']
 return json.loads(subprocess.check_output(args,text=True,timeout=30))['items']
r['nodes']=[{'name':x['metadata']['name'],'ready':any(c['type']=='Ready' and c['status']=='True' for c in x['status']['conditions'])} for x in get('nodes')]
r['pods']=[{'name':x['metadata']['name'],'namespace':x['metadata']['namespace'],'ready':any(c['type']=='Ready' and c['status']=='True' for c in x['status'].get('conditions',[])),'restarts':sum(c.get('restartCount',0) for c in x['status'].get('containerStatuses',[]))} for x in get('pods')]
r['volumes']=[{'name':x['metadata']['name'],'state':x['status'].get('state'),'robustness':x['status'].get('robustness')} for x in get('volumes.longhorn.io','longhorn-system')]
r['engines']=[{'name':x['metadata']['name'],'replicaModeMap':x['status'].get('replicaModeMap'),'rebuildStatus':x['status'].get('rebuildStatus')} for x in get('engines.longhorn.io','longhorn-system')]
print(json.dumps(r))
'''
rows=[]
for n in range(4):
 p=subprocess.run(['ssh','-o','BatchMode=yes','ubuntu@192.168.3.64','python3','-'],input=code,text=True,capture_output=True,timeout=150);assert p.returncode==0
 r=json.loads(p.stdout);rows.append(r);(root/'cluster-observations-final.json').write_text(json.dumps(rows,indent=2))
 print(json.dumps({'at':r['at'],'nodes_ready':sum(x['ready'] for x in r['nodes']),'pods_ready':sum(x['ready'] for x in r['pods']),'volumes':r['volumes'],'engines':r['engines']}),flush=True)
 if n<3:time.sleep(60)
