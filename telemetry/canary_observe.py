"""Save sanitized device state and stored flow records for the Part 8 canary."""
import json
import subprocess
import sys
import urllib.parse
import urllib.request

from canary_control import record

CODE = r'''
import concurrent.futures,json,logging
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
def collect(d):
    row={'name':d.name,'address':str(d.primary_ip4.host),'commands':{}}
    try:
        user=d.secrets_group.get_secret_value('Generic','username',obj=d)
        password=d.secrets_group.get_secret_value('Generic','password',obj=d)
        eos=d.platform.name=='arista_eos'
        with ConnectHandler(device_type='arista_eos' if eos else 'cisco_ios',host=row['address'],username=user,password=password,secret=password,session_log=None,conn_timeout=15,auth_timeout=20,banner_timeout=30) as c:
            c.enable()
            commands=(['show sflow','show sflow interfaces','show running-config | section sflow','show startup-config | section sflow','show bgp evpn summary','show interfaces counters rates'] if eos else ['show flow exporter PART8-EXPORT statistics','show flow monitor PART8-MONITOR statistics','show flow monitor PART8-MONITOR cache format table','show flow interface','show running-config | section ^flow','show startup-config | section ^flow','show ip bgp summary'])
            commands+=['show running-config | include ^logging','show startup-config | include ^logging']
            for command in commands:
                row['commands'][command]=c.send_command(command,read_timeout=40)
            row['cli_errors']=[k for k,v in row['commands'].items() if '% Invalid' in v or '% Error' in v]
    except Exception as e:
        row['error_type']=type(e).__name__
    return row
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    rows=list(pool.map(collect,Device.objects.filter(name__in=['CE1','DCA-Leaf01']).select_related('platform','primary_ip4','secrets_group')))
print(json.dumps(rows))
'''

if __name__ == '__main__':
    label = sys.argv[1]
    result = subprocess.run(['docker', 'exec', 'nautobot_docker_compose-nautobot-1',
        'nautobot-server', 'shell', '--interface', 'python', '--command', CODE],
        capture_output=True, text=True, timeout=180, check=True)
    rows = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('[')))
    record(label + '-devices', rows)
    for row in rows:
        print(json.dumps(row), flush=True)
    data = urllib.parse.urlencode({'query': '_time:30m | limit 200'}).encode()
    with urllib.request.urlopen('http://127.0.0.1:19428/select/logsql/query', data=data, timeout=30) as r:
        logs = [json.loads(line) for line in r.read().splitlines() if line]
    record(label + '-logs', logs)
    print('Stored records sampled:', len(logs), flush=True)
