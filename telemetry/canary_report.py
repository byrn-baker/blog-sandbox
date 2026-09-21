"""Collect final canary evidence without credentials or full environments."""
import datetime
import json
import subprocess
import urllib.parse
import urllib.request

from canary_control import record


def query(expression):
    data = urllib.parse.urlencode({'query': expression}).encode()
    with urllib.request.urlopen('http://127.0.0.1:19428/select/logsql/query', data=data, timeout=30) as response:
        return [json.loads(line) for line in response.read().splitlines() if line]


def kube(*args):
    return json.loads(subprocess.check_output(['kubectl', *args, '-o', 'json']))


if __name__ == '__main__':
    cutoff = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    window = f'_time:[2026-09-20T23:54:00Z,{cutoff}]'
    summary = {'cutoff': cutoff, 'window_start': '2026-09-20T23:54:00Z'}
    summary['flow_records'] = query(window + ' AND flow.type:* | stats by (flow.type, flow.sampler_address) count() as records')
    summary['tagged_syslog'] = query(window + ' AND "PART8-CANARY" | limit 10')
    summary['eos_samples'] = query(window + ' AND flow.type:sflow_5 AND flow.sampler_address:192.168.3.32 | limit 100')
    summary['netflow_examples'] = query(window + ' AND flow.type:netflow_v9 | limit 5')
    summary['controlled_flow_samples'] = query(window + ' AND flow.type:sflow_5 AND source.port:47776 AND destination.port:47777 | stats count() as records')
    summary['udp_workload'] = {'sent': 45000, 'received': 44403, 'missing': 597,
        'missing_percent': 597 / 45000 * 100,
        'scope': 'Application counters for 128-byte UDP payloads from 10.100.0.10:47776 to 10.100.0.20:47777; cause of missing datagrams not isolated'}
    summary['applications'] = [{'name': x['metadata']['name'], 'sync': x['status']['sync']['status'],
        'health': x['status']['health']['status']} for x in kube('get', 'applications', '-n', 'argocd')['items']]
    summary['nodes'] = [{'name': x['metadata']['name'], 'ready': next(c['status'] for c in x['status']['conditions'] if c['type'] == 'Ready')} for x in kube('get', 'nodes')['items']]
    summary['volumes'] = [{'name': x['metadata']['name'], 'health': x['status']['robustness'], 'state': x['status']['state']} for x in kube('get', 'volumes.longhorn.io', '-n', 'longhorn-system')['items']]
    code = '''
import json
from nautobot_golden_config.models import ConfigCompliance
from nautobot.extras.models import JobLogEntry
compliance=[{'device':c.device.name,'feature':c.rule.feature.name,'compliance':c.compliance,'missing':c.missing,'extra':c.extra} for c in ConfigCompliance.objects.filter(device__name__in=['CE1','DCA-Leaf01'],rule__feature__name__in=['flow_export','logging']).select_related('device','rule__feature')]
jobs={j:[{'level':r.log_level,'message':r.message} for r in JobLogEntry.objects.filter(job_result_id=j) if r.log_level in ['info','warning','error','failure']] for j in ['b29a068c-ea63-4368-97ee-71c3372ffe2e','952d8b3e-2b14-4814-90b2-3ba23eba7a18']}
print(json.dumps({'compliance':compliance,'deployment_logs':jobs}))
'''
    output = subprocess.check_output(['docker', 'exec', 'nautobot_docker_compose-nautobot-1',
        'nautobot-server', 'shell', '--interface', 'python', '--command', code], text=True)
    summary.update(json.loads(next(line for line in output.splitlines() if line.startswith('{'))))
    summary['collector_log_warnings'] = subprocess.check_output(['kubectl', 'logs', '-n', 'observability',
        'deployment/telemetry-canary', '--since=20m'], text=True).splitlines()
    summary['collector_log_warnings'] = [line for line in summary['collector_log_warnings'] if '\twarn\t' in line or '\terror\t' in line]
    record('summary', summary)
    print(json.dumps({k: summary[k] for k in ['cutoff', 'flow_records', 'controlled_flow_samples', 'udp_workload', 'compliance', 'applications']}, indent=2))
