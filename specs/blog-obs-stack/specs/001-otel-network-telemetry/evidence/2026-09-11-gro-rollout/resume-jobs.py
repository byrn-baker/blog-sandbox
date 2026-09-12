import sys,json,pathlib,time
sys.path.insert(0,'/tmp')
from router_gc_api import api
root=pathlib.Path('/home/ubuntu/gro-rollout')
def wait(jid):
 for _ in range(240):
  x=api('extras/job-results/'+jid+'/');s=x['status']['value']
  if s not in ['PENDING','STARTED','RUNNING','RECEIVED','RETRY']:
   logs=api('extras/job-results/'+jid+'/logs/')
   bad=[{'level':l['log_level'],'message':l['message'],'object':l.get('log_object')} for l in logs if l['log_level'] in ['error','failure','critical']]
   (root/(jid+'-result.json')).write_text(json.dumps({'status':s,'errors':bad},indent=2))
   print(jid,s,'errors',len(bad),flush=True)
   assert s=='SUCCESS' and not bad,(jid,s,bad)
   return x
  time.sleep(5)
 raise TimeoutError(jid)
def run(label,jid,data):
 x=api('extras/jobs/'+jid+'/run/',{'data':data});(root/(label+'-job.json')).write_text(json.dumps(x));jid=x['job_result']['id'];print(label,jid,flush=True);return wait(jid)
if __name__=='__main__':
 ids=[x['id'] for x in json.loads((root/'leaf-audit.json').read_text())]
 # Sync already verified successful; resume remaining preparation.
 run('loader','e7a2f582-3a18-4f75-b387-24d022aabfa6',{})
 for label,jid,extra in [('intended','ab420817-1d1f-4d56-a319-382be6970919',{'commit_message':'Render approved persistent leaf GRO correction'}),('backup','f2033b99-24cd-4949-be4e-ed79d8178850',{'commit_message':'Leaf baseline before persistent GRO correction'}),('compliance','6ffd11a2-7e95-4b93-b900-e134eaee1d4d',{})]:
  run(label,jid,{'device':ids,'debug':False,'fail_job_on_task_failure':True,**extra})
