"""Match a completed transfer to stored sFlow records, retaining raw evidence."""
import argparse
import datetime
import json
from pathlib import Path
import urllib.parse
import urllib.request


def query(text):
    req=urllib.request.Request('http://127.0.0.1:19428/select/logsql/query',
        data=urllib.parse.urlencode({'query':text}).encode())
    with urllib.request.urlopen(req,timeout=60) as r:
        return [json.loads(line) for line in r if line.strip()]


def verify(report,require_enrichment=False):
    assert report['verified']
    start=report['started_at']
    end=(datetime.datetime.fromisoformat(report['ended_at'])+datetime.timedelta(seconds=60)).isoformat()
    fields={'flow.type':'sflow_5','source.address':report['source_address'],
            'destination.address':report['destination_address'],
            'source.port':str(report['sender']['source_port']),
            'destination.port':str(report['destination_port']),'network.transport':'tcp'}
    selector=f'_time:[{start}, {end}] AND '+' AND '.join(k+':'+json.dumps(v) for k,v in fields.items())
    records=query(selector+' | limit 500')
    assert records,'No exact forward TCP samples found'
    counts={}
    for r in records:
        assert all(r[k]==v for k,v in fields.items())
        counts[r['flow.sampler_address']]=counts.get(r['flow.sampler_address'],0)+1
        if require_enrichment:
            assert r['nautobot.source.status']=='exact'
            assert r['nautobot.destination.status']=='exact'
            assert r['nautobot.source.label'].startswith(report['source_device']+' / ')
            assert r['nautobot.destination.label'].startswith(report['destination_device']+' / ')
            assert r['nautobot.exporter.status']=='exact'
    return {'query':selector,'matching_samples':len(records),'by_exporter':counts,
            'require_enrichment':require_enrichment,'records':records}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('report',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--require-enrichment',action='store_true')
    a=p.parse_args()
    result=verify(json.loads(a.report.read_text()),a.require_enrichment)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
