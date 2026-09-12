import json
from jobs import run,root
ids=[x['id'] for x in json.loads((root/'leaf-audit.json').read_text())]
for label,jid,extra in [('final-backup','f2033b99-24cd-4949-be4e-ed79d8178850',{'commit_message':'Backups after approved persistent leaf GRO rollout'}),('final-compliance','6ffd11a2-7e95-4b93-b900-e134eaee1d4d',{})]:
 run(label,jid,{'device':ids,'debug':False,'fail_job_on_task_failure':True,**extra})
