import sys,json,urllib.request
from jobs import root,api,run
from router_gc_api import val
rows=json.loads((root/'recovery-verified.json').read_text());names=sys.argv[1:];assert names and len(set(names))==len(names)
selected=[]
for name in names:
 r=next(r for r in rows if r['name']==name);p=api('plugins/golden-config/config-plan/'+r['plan_id']+'/')
 assert p['config_set'].strip()==r['commands'].strip() and not p.get('deploy_result')
 req=urllib.request.Request(val('NAUTOBOT_URL').rstrip('/')+'/api/plugins/golden-config/config-plan/'+p['id']+'/',method='PATCH',data=json.dumps({'status':'0a682c72-aae8-498c-8d18-d686ead4bb74'}).encode(),headers={'Authorization':'Token '+val('NAUTOBOT_TOKEN'),'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:assert response.status==200
 selected.append(p['id'])
run('recovery-deploy-'+'-'.join(names),'7c91d376-a0e9-4178-96fe-7b80954ced04',{'config_plan':selected,'fail_job_on_task_failure':True,'debug':False})
