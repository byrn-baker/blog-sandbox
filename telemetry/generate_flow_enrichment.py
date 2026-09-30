"""Generate a non-secret Nautobot address snapshot and OTel enrichment processor.

Exact assigned-IP matches only. Shared addresses retain all owners; cross-
namespace collisions remain ambiguous because the flow decoder has no VRF.
No network calls occur per flow. Publish generated values through GitOps.
"""
import argparse
from collections import defaultdict
import datetime
import hashlib
import ipaddress
import json
from pathlib import Path

import yaml
from canary_control import api

ROOT = Path(__file__).resolve().parents[1]


def build_snapshot(response):
    if response.get('errors') or not response.get('data',{}).get('devices'):
        raise ValueError('Nautobot query failed or empty; existing snapshot preserved')
    entries=defaultdict(set)
    devices=response['data']['devices']
    names=set()
    for d in devices:
        if d['name'] in names: raise ValueError('Duplicate device')
        names.add(d['name'])
        for interface in d['interfaces']:
            for ip in interface['ip_addresses']:
                address=str(ipaddress.ip_interface(ip['address']).ip)
                namespace=ip['parent']['namespace']['name']
                if not namespace: raise ValueError('Missing namespace')
                entries[address].add((namespace,d['name'],interface['name'],
                                     d['location']['name'],d['role']['name']))
    if not entries: raise ValueError('No assigned addresses; existing snapshot preserved')
    addresses={}
    for ip,owners in sorted(entries.items()):
        namespaces=sorted({x[0] for x in owners})
        status='ambiguous' if len(namespaces)>1 else ('shared' if len(owners)>1 else 'exact')
        labels=[f'{device} / {interface} ({site})' for _,device,interface,site,_ in sorted(owners)]
        addresses[ip]={'status':status,'label':'; '.join(labels) if status!='ambiguous' else 'ambiguous namespace: '+ip,
                       'namespace':', '.join(namespaces),
                       'owners':[dict(zip(['namespace','device','interface','site','role'],o)) for o in sorted(owners)]}
    digest=hashlib.sha256(json.dumps(addresses,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'sha256':digest,'generated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'device_count':len(devices),'addresses':addresses}


def processor(snapshot):
    # Only labels/status/namespace enter the lookup table; full ownership remains
    # in the auditable snapshot. Original flow fields are never replaced.
    table={ip:{k:r[k] for k in ['label','status','namespace']} for ip,r in snapshot['addresses'].items()}
    statements=['set(cache["sot"], ParseJSON('+json.dumps(json.dumps(table,separators=(',',':')))+'))']
    for field in ['sha256','generated_at']:
        statements.append('set(attributes["nautobot.snapshot.'+field+'"], '+json.dumps(snapshot[field])+')')
    for role,key in [('source','source.address'),('destination','destination.address'),('exporter','flow.sampler_address')]:
        lookup='cache["sot"][attributes['+json.dumps(key)+']]'
        statements.append(f'set(attributes["nautobot.{role}.status"], "unknown") where attributes["{key}"] != nil')
        for field in ['label','status','namespace']:
            statements.append(f'set(attributes["nautobot.{role}.{field}"], {lookup}["{field}"]) where {lookup} != nil')
    return {'error_mode':'ignore','log_statements':[{'context':'log',
        'conditions':['attributes["flow.type"] != nil'],'statements':statements}]}


def enrich_record(record,snapshot):
    """Read-only report enrichment using the same mapping; not historical ownership."""
    result=dict(record)
    for role,key in [('source','source.address'),('destination','destination.address'),('exporter','flow.sampler_address')]:
        if key not in record: continue
        entry=snapshot['addresses'].get(record[key],{'status':'unknown'})
        for field in ['label','status','namespace']:
            if field in entry: result[f'nautobot.{role}.{field}']=entry[field]
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--snapshot',type=Path,required=True)
    a=p.parse_args()
    snapshot=build_snapshot(api('graphql/',{'query':(ROOT/'queries/flow_enrichment.gql').read_text()}))
    # Validate everything before opening either output. Replace via temporary
    # sibling files so a failed fetch never truncates the deployed generation.
    payloads=[(a.output,yaml.safe_dump({'enrichment':processor(snapshot)},sort_keys=False)),
              (a.snapshot,json.dumps(snapshot,indent=2)+'\n')]
    for path,payload in payloads:
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+'.tmp')
        with tmp.open('x') as f: f.write(payload)
        tmp.replace(path)
    print(json.dumps({'devices':snapshot['device_count'],'addresses':len(snapshot['addresses']),
                      'sha256':snapshot['sha256']}))


if __name__=='__main__': main()
