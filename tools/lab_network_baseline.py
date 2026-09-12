#!/usr/bin/env python3
"""Read-only pyATS samples, checked against live Nautobot inventory."""
import argparse
import concurrent.futures
import datetime
import json
import logging
import os
from pathlib import Path
import re
import time
import urllib.request
import warnings

from pyats.topology import loader


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--devices', nargs='*')
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"unicon\..*")
    settings = json.loads(args.settings.read_text())['mcpServers']
    env = settings['nautobot-mcp']['env']

    def value(key):
        val = os.environ.get(key, env.get(key, ''))
        if val.startswith('${') and val.endswith('}'):
            return os.environ[val[2:-1]]
        return val

    request = urllib.request.Request(
        value('NAUTOBOT_URL').rstrip('/') + '/api/graphql/',
        data=json.dumps({'query': '{ devices { name role { name } primary_ip4 { host } } }'}).encode(),
        headers={'Authorization': 'Token ' + value('NAUTOBOT_TOKEN'), 'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    if payload.get('errors'):
        raise RuntimeError('Nautobot inventory query failed')
    fleet = {d['name']: d['primary_ip4']['host'] for d in payload['data']['devices']
             if d['role']['name'] in ['Border-Router', 'CE-Router', 'P-Router', 'PE-Router', 'Route-Reflector', 'Leaf', 'Spine']}
    if not fleet:
        raise RuntimeError('Empty network inventory')
    tb = loader.load(settings['pyats-mcp']['env']['PYATS_TESTBED_PATH'])
    selected = sorted(args.devices or fleet)
    for name in selected:
        if name not in fleet or name not in tb.devices or str(tb.devices[name].connections.cli.ip) != fleet[name]:
            raise RuntimeError('Inventory mismatch for ' + name)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'inventory.json').write_text(json.dumps({'at': now(), 'devices': {n: fleet[n] for n in selected}}, indent=2))

    def collect(name):
        device = tb.devices[name]
        row = {'name': name, 'started': now(), 'os': device.os, 'commands': []}
        commands = {
            'iosxe': ['show platform hardware throughput level', 'show platform hardware qfp active datapath utilization',
                      'show platform hardware qfp active statistics drop', 'show ip ospf neighbor', 'show ip bgp summary'],
            'eos': ['show interfaces counters discards', 'show interfaces counters rates', 'show bgp evpn summary'],
        }
        if device.os not in commands:
            row['error'] = 'Unsupported OS'
        else:
            try:
                device.connect(learn_hostname=True, log_stdout=False, logfile='/dev/null',
                               init_exec_commands=['terminal length 0'], init_config_commands=[], connection_timeout=60)
                row['connected'] = True
                for command in commands[device.os]:
                    item = {'command': command, 'at': now()}
                    try:
                        item['output'] = device.execute(command, timeout=30)
                        item['ok'] = not bool(re.search(r'% (?:Invalid|Incomplete|Ambiguous|Unavailable)', item['output']))
                    except Exception as exc:
                        item.update(ok=False, error=type(exc).__name__)
                    row['commands'].append(item)
                    if 'error' in item:
                        break  # avoid issuing commands into an unsynchronized session
                if row['commands'] and all(x['ok'] for x in row['commands']):
                    time.sleep(10)
                    command = commands[device.os][0 if device.os == 'eos' else 2]
                    item = {'command': command, 'at': now()}
                    try:
                        item.update(output=device.execute(command, timeout=30), ok=True)
                    except Exception as exc:
                        item.update(ok=False, error=type(exc).__name__)
                    row['commands'].append(item)
            except Exception as exc:
                row['error'] = type(exc).__name__
                row['error_chain'] = []
                current = exc
                while current is not None and len(row['error_chain']) < 5:
                    message = str(current).lower()
                    row['error_chain'].append({'type': type(current).__name__, 'signals': [term for term in ['authentication failed', 'permission denied', 'connection refused', 'timed out', 'timeout', 'hostname', 'password', 'enable'] if term in message]})
                    current = current.__cause__ or current.__context__
            finally:
                try:
                    device.disconnect()
                except Exception:
                    pass
        row['finished'] = now()
        # Outputs are restricted to the command allowlist; no configs or session logs.
        (args.output / (name + '.json')).write_text(json.dumps(row, indent=2))
        result = {'name': name, 'connected': row.get('connected', False),
                  'commands_ok': sum(x['ok'] for x in row['commands']), 'error': row.get('error')}
        print(json.dumps(result), flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(collect, selected))
    (args.output / 'summary.json').write_text(json.dumps({'finished': now(), 'results': results}, indent=2))


if __name__ == '__main__':
    main()
