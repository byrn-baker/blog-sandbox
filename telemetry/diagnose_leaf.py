"""Read selected DCA-Leaf01 counters without changing device state."""
import json
import subprocess
import sys
from diagnose_udp import save

CODE = r'''
import json,logging,datetime
from nautobot.dcim.models import Device
from netmiko import ConnectHandler
logging.disable(logging.CRITICAL)
d=Device.objects.get(name='DCA-Leaf01')
u=d.secrets_group.get_secret_value('Generic','username',obj=d)
p=d.secrets_group.get_secret_value('Generic','password',obj=d)
with ConnectHandler(device_type='arista_eos',host=str(d.primary_ip4.host),username=u,password=p,secret=p,session_log=None) as c:
 c.enable()
 cmds=['show interfaces counters discards','show interfaces counters errors',
       'bash ip -s link show vmnicet1','bash ip -s link show vmnicet4',
       'bash ethtool -S vmnicet1','bash ethtool -S vmnicet4',
       'bash cat /proc/net/softnet_stat','bash cat /proc/net/snmp',
       'bash ps -p 2108,1836,10894 -o pid,comm,pcpu,time',
       'show interfaces Ethernet1 hardware','show interfaces Ethernet4 hardware']
 print(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'commands':{cmd:c.send_command(cmd,read_timeout=30) for cmd in cmds}}))
'''

if __name__ == '__main__':
    p = subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1',
        'nautobot-server','shell','--interface','python','--command',CODE],
        capture_output=True,text=True,check=True,timeout=180)
    result=json.loads(next(x for x in p.stdout.splitlines() if x.startswith('{')))
    save(sys.argv[1],result)
    print(json.dumps(result))
