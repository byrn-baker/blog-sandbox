"""Bounded, sequence-numbered host UDP diagnostics over existing SSH access.

No configuration changes. Receiver readiness is observed before sending.
The receiver allows a four-second idle tail, with a 60-second hard limit.
"""
import json
import subprocess
import time
import tempfile
import re
import struct
from pathlib import Path

EVIDENCE = Path(__file__).parent / 'evidence' / 'udp-diagnosis-20260921'

def save(label, result):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / (label+'.json')).write_text(json.dumps(result, indent=2)+'\n')

REMOTE = r'''
import json, socket, sys, time
mode, address, peer, count, port, interval = sys.argv[1:]
count, port = int(count), int(port)
interval = float(interval)
def counters():
    rows = open('/proc/net/snmp').read().splitlines()
    result = {}
    for i in range(0, len(rows), 2):
        keys, vals = rows[i].split(), rows[i+1].split()
        if keys[0] in ['Udp:', 'Ip:', 'Tcp:']:
            result[keys[0][:-1]] = dict(zip(keys[1:], map(int, vals[1:])))
    return result
before = counters()
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((address, port if mode == 'receive' else port-1))
start = time.monotonic()
if mode == 'receive':
    s.settimeout(1)
    seen, duplicates, last = set(), 0, None
    print('READY', flush=True)
    while time.monotonic()-start < 60:
        try:
            data, source = s.recvfrom(2048)
        except socket.timeout:
            if last is not None and time.monotonic()-last > 4:
                break
            continue
        if source[0] != peer or not data.startswith(b'UDP-DIAG:'):
            continue
        seq = int(data[9:].split(b':', 1)[0])
        duplicates += seq in seen
        seen.add(seq)
        last = time.monotonic()
    missing = sorted(set(range(count))-seen)
    result = dict(received=len(seen), duplicates=duplicates,
                  first=min(seen) if seen else None, last=max(seen) if seen else None,
                  missing=missing)
else:
    for seq in range(count):
        payload = ('UDP-DIAG:%d:' % seq).encode().ljust(128, b'.')
        s.sendto(payload, (peer, port))
        time.sleep(interval)
    result = dict(sent=count)
after = counters()
result.update(elapsed=time.monotonic()-start, address=address,
              counters={p:{k:v-before[p][k] for k,v in vals.items()
                           if v != before[p][k]} for p,vals in after.items()})
print(json.dumps(result), flush=True)
'''

def command(host, mode, address, peer, count, port, interval=0.004):
    import shlex
    return ['ssh', '-o', 'BatchMode=yes', 'ubuntu@'+host,
            'python3 -u -c '+shlex.quote(REMOTE)+' '+
            ' '.join(map(shlex.quote, [mode,address,peer,str(count),str(port),str(interval)]))]

def run(label, source_host, target_host, source, target, port, count=5000, interval=0.004):
    assert 0<count<=5000 and interval>=0.004 and count*interval<=25
    receiver = subprocess.Popen(command(target_host,'receive',target,source,count,port),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert receiver.stdout.readline().strip() == 'READY', 'Receiver not ready'
    sender = subprocess.run(command(source_host,'send',source,target,count,port,interval),
                            capture_output=True, text=True, timeout=50, check=True)
    output, errors = receiver.communicate(timeout=15)
    assert receiver.returncode == 0, errors
    result = dict(test=label, requested_interval=interval,
                  sender=json.loads(sender.stdout),receiver=json.loads(output))
    save(label, result)
    print(json.dumps({'test':label,'sent':count,'received':result['receiver']['received']}),flush=True)
    return result

def captured_run(reverse=False, suffix=''):
    stats_code = """import json,time,pathlib
rows=[]
interfaces = ['vunl0_3_1','vunl0_3_4','eth9','vunl0_9_4','eth16',
              'vunl0_9_1','vunl0_6_2','vunl0_6_10','eth5','eth3','vunl0_1_10','vunl0_1_1']
interfaces += [p.resolve().name for iface in list(interfaces)
               if (p:=pathlib.Path('/sys/class/net')/iface/'master').exists()]
interfaces = sorted(set(interfaces))
for i in range(40):
 row={'time':time.time(),'interfaces':{}}
 for iface in interfaces:
  base=pathlib.Path('/sys/class/net')/iface/'statistics'
  row['interfaces'][iface]={k:int((base/k).read_text()) for k in ['rx_packets','tx_packets','rx_dropped','tx_dropped','rx_errors','tx_errors']}
 rows.append(row);time.sleep(1)
print(json.dumps(rows))
"""
    import shlex
    stats = subprocess.Popen(['ssh','-o','BatchMode=yes','root@192.168.17.2',
        'python3 -c '+shlex.quote(stats_code)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    captures = []
    port = 47879 if reverse else 47877
    for host in ['192.168.3.63', '192.168.3.66', '192.168.17.2']:
        output = tempfile.TemporaryFile()
        eve = host == '192.168.17.2'
        flt = 'udp dst port %d' % port
        if eve:
            flt += ' or (udp dst port 4789 and udp[52:2] = %d)' % port
        proc = subprocess.Popen(['ssh','-o','BatchMode=yes',('root@' if eve else 'ubuntu@')+host,
            "sudo -n timeout 38 tcpdump -U -n -i %s -s 300 -w - '%s'" % ('any' if eve else 'bond0',flt)],
            stdout=output, stderr=subprocess.PIPE, text=True)
        line = proc.stderr.readline()
        while line and 'listening on' not in line:
            line = proc.stderr.readline()
        assert 'listening on' in line, 'Capture failed to start'
        captures.append((host,proc,output))
    label = ('fabric-reverse-captured' if reverse else 'fabric-forward-captured')+suffix
    result = (run(label,'192.168.3.66','192.168.3.63','10.100.0.20','10.100.0.10',port)
              if reverse else run(label,'192.168.3.63','192.168.3.66','10.100.0.10','10.100.0.20',port))
    result['captures'] = {}
    for host, proc, output in captures:
        _, stderr = proc.communicate(timeout=45)
        output.seek(0)
        raw = output.read()
        endian = '<' if raw[:4] == b'\xd4\xc3\xb2\xa1' else '>'
        linktype = struct.unpack(endian+'I',raw[20:24])[0]
        packets = []
        offset = 24
        while offset+16 <= len(raw):
            sec,usec,length,original = struct.unpack(endian+'IIII',raw[offset:offset+16])
            packet = raw[offset+16:offset+16+length]
            offset += 16+length
            match = re.search(rb'UDP-DIAG:(\d+):',packet)
            if match:
                ip = packet[20:] if linktype == 276 else packet[14:]
                ihl = (ip[0]&15)*4
                packets.append({'seq':int(match[1]),'time':sec+usec/1000000,
                    'interface':int.from_bytes(packet[4:8],'big') if linktype==276 else 'bond0',
                    'direction':packet[10] if linktype==276 else None,
                    'source':'.'.join(map(str,ip[12:16])), 'destination':'.'.join(map(str,ip[16:20])),
                    'sport':int.from_bytes(ip[ihl:ihl+2],'big'), 'dport':int.from_bytes(ip[ihl+2:ihl+4],'big')})
        seqs = [p['seq'] for p in packets]
        result['captures'][host] = dict(packets=len(seqs),unique=len(set(seqs)),
            missing=sorted(set(range(5000))-set(seqs)),capture_summary=stderr,linktype=linktype)
        save(label+'-'+host+'-packets',packets)
        output.close()
    save(label,result)
    output, errors = stats.communicate(timeout=15)
    assert stats.returncode == 0, errors
    samples = json.loads(output)
    save(label+'-eve-counters',samples)
    print(json.dumps({'counter_deltas':{iface:{k:v-samples[0]['interfaces'][iface][k]
        for k,v in vals.items()} for iface,vals in samples[-1]['interfaces'].items()}}),flush=True)
    print(json.dumps({h:{k:v for k,v in c.items() if k!='missing'} for h,c in result['captures'].items()}),flush=True)
    return result

if __name__ == '__main__':
    import sys
    if '--capture' in sys.argv:
        captured_run('--reverse' in sys.argv, '-repeat' if '--repeat' in sys.argv else '')
        sys.exit()
    run('fabric-forward','192.168.3.63','192.168.3.66','10.100.0.10','10.100.0.20',47877)
    run('management-forward','192.168.3.63','192.168.3.66','192.168.3.63','192.168.3.66',47878)
    run('fabric-reverse','192.168.3.66','192.168.3.63','10.100.0.20','10.100.0.10',47879)
