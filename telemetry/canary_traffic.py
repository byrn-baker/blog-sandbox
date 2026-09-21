"""Bounded UDP workload for observing real inter-site flow samples.

The receiver exits after 210 seconds; sender caps at 250 packets/s for 180
seconds. The payload is a synthetic marker. No network configuration changes.
"""
import argparse
import json
import socket
import time

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['receive', 'send'])
    args = p.parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        if args.mode == 'receive':
            s.bind(('10.100.0.20', 47777))
            s.settimeout(1)
            until = time.monotonic() + 210
            count = 0
            while time.monotonic() < until:
                try:
                    data, address = s.recvfrom(1024)
                    if data.startswith(b'PART8-CANARY-') and address[0] == '10.100.0.10':
                        count += 1
                except socket.timeout:
                    pass
            print(json.dumps({'received': count, 'destination': '10.100.0.20:47777'}), flush=True)
        else:
            s.bind(('10.100.0.10', 47776))
            for count in range(45000):
                s.sendto(('PART8-CANARY-' + str(count)).encode().ljust(128, b'.'), ('10.100.0.20', 47777))
                time.sleep(0.004)
            print(json.dumps({'sent': 45000, 'source': '10.100.0.10:47776', 'destination': '10.100.0.20:47777'}), flush=True)
