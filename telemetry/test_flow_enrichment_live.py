"""Exercise generated OTTL with synthetic OTLP records in the pinned local image.

This tests the processor, not packet sampling. No lab records are injected.
"""
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

import yaml
from generate_flow_enrichment import build_snapshot,processor
from test_flow_enrichment import device


def main():
    snapshot=build_snapshot({'data':{'devices':[device(),device('leaf2'),
        device('server',address='10.100.0.10/24'),device('tenant1','A','10.0.0.1/32'),
        device('tenant2','B','10.0.0.1/32')]}})
    config={'receivers':{'otlp':{'protocols':{'http':{'endpoint':'0.0.0.0:4318'}}}},
            'processors':{'transform/nautobot':processor(snapshot)},
            'exporters':{'debug':{'verbosity':'detailed'}},
            'service':{'pipelines':{'logs':{'receivers':['otlp'],
                'processors':['transform/nautobot'],'exporters':['debug']}}}}
    with tempfile.TemporaryDirectory(prefix='flow-enrichment-test-') as temp:
        path=Path(temp)/'collector.yaml'; path.write_text(yaml.safe_dump(config))
        cid=subprocess.check_output(['docker','run','-d','--rm','--user','0','--read-only',
            '--cap-drop','ALL','--memory','256m','--cpus','0.5','-p','127.0.0.1::4318',
            '-v',str(path)+':/conf.yaml:ro','otel/opentelemetry-collector-contrib:0.154.0',
            '--config=/conf.yaml'],text=True).strip()
        try:
            port=int(subprocess.check_output(['docker','port',cid,'4318'],text=True).strip().rsplit(':',1)[1])
            for _ in range(50):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/logs',timeout=1)
                    break
                except urllib.error.HTTPError as e:
                    if e.code==405: break
                    raise
                except OSError: time.sleep(.2)
            else: raise RuntimeError('Collector did not become ready')
            logs=[]
            for source in ['10.100.0.10','10.3.1.1','10.0.0.1','198.51.100.99']:
                attrs={'flow.type':'sflow_5','source.address':source,'destination.address':'10.100.0.10',
                       'flow.sampler_address':'10.3.1.1','flow.io.bytes':'123'}
                logs.append({'body':{'stringValue':'processor-test'},'attributes':[
                    {'key':k,'value':{'stringValue':v}} for k,v in attrs.items()]})
            payload={'resourceLogs':[{'scopeLogs':[{'logRecords':logs}]}]}
            req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/logs',data=json.dumps(payload).encode(),
                headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r: assert r.status==200
            time.sleep(1)
            result=subprocess.run(['docker','logs',cid],capture_output=True,text=True,check=True)
            output=result.stdout+result.stderr
            for status in ['exact','shared','ambiguous','unknown']:
                assert f'nautobot.source.status: Str({status})' in output,status
            assert 'nautobot.source.label: Str(server / Loopback1 (DC-A))' in output
            assert output.count('flow.io.bytes: Str(123)')==4
            assert 'failed to execute' not in output.lower()
            print(json.dumps({'passed':True,'records':4,'cases':['exact','shared','ambiguous','unknown'],
                              'original_bytes_preserved':True,'image':'0.154.0'}))
        except Exception:
            r=subprocess.run(['docker','logs',cid],capture_output=True,text=True)
            print((r.stdout+r.stderr)[-5000:])
            raise
        finally: subprocess.run(['docker','stop','-t','2',cid],stdout=subprocess.DEVNULL,check=True)


if __name__=='__main__': main()
