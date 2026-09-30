"""Bounded lab TCP file transfer; inventory comes from Nautobot, no device writes.

Creates temporary files on the selected hosts and removes them on normal exit.
SSH uses existing keys. The listener is bound to the modeled data IP only.
"""
import argparse
import datetime
import ipaddress
import json
from pathlib import Path
import shlex
import subprocess
import time

from canary_control import api

QUERY = '{ devices { name role { name } primary_ip4 { address } interfaces { name ip_addresses { address } } } }'
REMOTE = r'''
import hashlib,json,os,signal,socket,sys,tempfile,time
mode,source,dest,port,size,rate=sys.argv[1:]
port,size,rate=map(int,(port,size,rate))
signal.signal(signal.SIGALRM,lambda *args:sys.exit('Transfer deadline exceeded'))
signal.alarm(720)
block=bytes(range(256))*256
with tempfile.TemporaryFile(prefix='part8-sflow-',dir='/var/tmp') as f:
 if mode=='receive':
  with socket.socket() as listener:
   listener.settimeout(30); listener.bind((dest,port)); listener.listen(1)
   print(json.dumps({'ready':True}),flush=True)
   conn,peer=listener.accept()
   with conn:
    assert peer[0]==source,peer
    conn.settimeout(60); start=time.monotonic(); total=0
    while True:
     data=conn.recv(65536)
     if not data: break
     total+=len(data)
     assert total<=size,'Unexpected extra data'
     f.write(data)
    elapsed=time.monotonic()-start
   assert total==size,(total,size)
 else:
  for _ in range(size//len(block)): f.write(block)
  f.flush(); f.seek(0)
  with socket.socket() as conn:
   conn.setsockopt(socket.IPPROTO_TCP,socket.TCP_MAXSEG,1200)
   conn.settimeout(60); conn.bind((source,0)); conn.connect((dest,port))
   source_port=conn.getsockname()[1]; start=time.monotonic(); total=0
   while data:=f.read(16384):
    conn.sendall(data); total+=len(data)
    time.sleep(max(0,total/rate-(time.monotonic()-start)))
   conn.shutdown(socket.SHUT_WR)
   elapsed=time.monotonic()-start
 f.flush(); f.seek(0); digest=hashlib.file_digest(f,'sha256').hexdigest()
 result={'mode':mode,'bytes':total,'seconds':elapsed,'sha256':digest}
 if mode=='send': result['source_port']=source_port
 print(json.dumps(result),flush=True)
'''


def endpoint(devices, name):
    d = next(d for d in devices if d['name'] == name)
    assert d['role']['name'] == 'Server'
    ips = [str(ipaddress.ip_interface(ip['address']).ip) for i in d['interfaces']
           if i['name'] == 'bond0' for ip in i['ip_addresses']
           if ipaddress.ip_interface(ip['address']).version == 4]
    assert len(ips) == 1 and ipaddress.ip_address(ips[0]) in ipaddress.ip_network('10.100.0.0/24')
    return str(ipaddress.ip_interface(d['primary_ip4']['address']).ip), ips[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', default='DCA-k3s-m1')
    p.add_argument('--destination', default='DCC-k3s-w4')
    p.add_argument('--mib', type=int, default=256)
    p.add_argument('--port', type=int, default=47931)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    assert 16 <= a.mib <= 256 and 4910 <= a.port <= 65535
    response = api('graphql/', {'query':QUERY})
    assert not response.get('errors')
    devices = response['data']['devices']
    sm, source = endpoint(devices,a.source); dm, dest = endpoint(devices,a.destination)
    assert source != dest
    def command(host,mode):
        return ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','ubuntu@'+host,
                'python3 -c '+shlex.quote(REMOTE)+' '+shlex.join(
                    [mode,source,dest,str(a.port),str(a.mib*1048576),str(1048576)])]
    for host,expected,other in [(sm,a.source,dest),(dm,a.destination,source)]:
        actual=subprocess.check_output(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',
            'ubuntu@'+host,'hostname'],text=True).strip()
        assert actual.lower()==expected.lower(),(actual,expected)
        route=subprocess.check_output(['ssh','-o','BatchMode=yes','ubuntu@'+host,
            'ip -4 route get '+other],text=True)
        assert 'dev bond0' in route,route
    report={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'source_device':a.source,'destination_device':a.destination,
            'source_address':source,'destination_address':dest,'destination_port':a.port,
            'rate_limit_bytes_per_second':1048576}
    report['requested_tcp_mss']=1200
    receiver=subprocess.Popen(command(dm,'receive'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert json.loads(receiver.stdout.readline())['ready']
        print(json.dumps({'started':report}),flush=True)
        sender=subprocess.run(command(sm,'send'),capture_output=True,text=True,timeout=730,check=True)
        out,err=receiver.communicate(timeout=75)
        assert receiver.returncode==0,err
        report.update(sender=json.loads(sender.stdout),receiver=json.loads(out),
                      ended_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        assert report['sender']['sha256']==report['receiver']['sha256']
        assert report['sender']['bytes']==report['receiver']['bytes']==a.mib*1048576
        report['verified']=True
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
    finally:
        if receiver.poll() is None:
            receiver.terminate()
            receiver.communicate(timeout=10)


if __name__=='__main__': main()
