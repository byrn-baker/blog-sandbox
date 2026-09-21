"""Read final comparison state and regenerate missing-feature Plans only."""
import datetime
import json
import urllib.parse
import urllib.request
from sflow_ab import control, django, device
from canary_report import kube
from sflow_ab_report import summarize


def query(expression):
    data=urllib.parse.urlencode({'query':expression}).encode()
    with urllib.request.urlopen('http://127.0.0.1:19428/select/logsql/query',data,timeout=30) as r:
        return [json.loads(x) for x in r.read().splitlines() if x]


if __name__=='__main__':
    features=control.api('plugins/golden-config/compliance-feature/?limit=200')['results']
    ids=[x['id'] for x in features if x['name'] in ['flow_export','logging']]
    assert len(ids)==2
    job=control.run('82a6fe32-9897-4acc-ba8b-f6d0849d9717',
        {'device':[device()],'plan_type':'missing','feature':ids,
         'change_control_id':'part8-sflow-ab-20260921-final','debug':False},'final-plans')
    code='''
import json
from nautobot_golden_config.models import ConfigCompliance,ConfigPlan
from nautobot.extras.models import JobLogEntry
rows=[{'feature':c.rule.feature.name,'compliance':c.compliance,'missing':c.missing,'extra':c.extra}
 for c in ConfigCompliance.objects.filter(device__name='DCA-Leaf01',rule__feature__name__in=['flow_export','logging']).select_related('rule__feature')]
print(json.dumps({'compliance':rows,
 'plans':list(ConfigPlan.objects.filter(change_control_id='part8-sflow-ab-20260921-final').values('config_set')),
 'plan_logs':list(JobLogEntry.objects.filter(job_result_id=JOB).values('log_level','message'))}))
'''.replace('JOB',repr(job['id']))
    result=django(code)
    assert len(result['compliance'])==2 and all(x['compliance'] for x in result['compliance'])
    assert not result['plans'], 'Unexpected final missing configuration'
    result['cutoff']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['nodes']=[{'name':x['metadata']['name'],'ready':next(c['status'] for c in x['status']['conditions'] if c['type']=='Ready')} for x in kube('get','nodes')['items']]
    result['applications']=[{'name':x['metadata']['name'],'sync':x['status']['sync']['status'],'health':x['status']['health']['status']} for x in kube('get','applications','-n','argocd')['items']]
    result['volumes']=[{'name':x['metadata']['name'],'health':x['status']['robustness']} for x in kube('get','volumes.longhorn.io','-n','longhorn-system')['items']]
    result['traced_netflow']=query('_time:[2026-09-21T01:52:00Z,2026-09-21T03:00:00Z] flow.type:netflow_v9 source.address:10.3.2.5 destination.address:10.3.1.4 source.port:7966 destination.port:4789 | limit 100')
    result['restored_sflow']=query('_time:[2026-09-21T02:00:00Z,2026-09-21T03:00:00Z] flow.type:sflow_5 flow.sampler_address:192.168.3.32 | limit 20')
    control.record('final-audit',result)
    summarize()
    print(json.dumps({'compliance':result['compliance'],'missing_plans':result['plans'],
        'netflow_records':len(result['traced_netflow']),'restored_sflow_records':len(result['restored_sflow'])}),flush=True)
