"""Summarize matched packet paths, bridge delay and socket pressure."""
import collections
import json
import re
import statistics
from sflow_ab import EVIDENCE


def summarize():
    result = {}
    for label in ['on-before','off','on-restored']:
        path=EVIDENCE/(label+'-eve-links.json')
        if not path.exists():continue
        links={x['ifindex']:x['ifname'] for x in json.loads(path.read_text())}
        runs=[]
        for i in [1,2]:
            base='fabric-reverse-captured-'+label+'-'+str(i)
            if not (EVIDENCE/(base+'-192.168.17.2-packets.json')).exists():continue
            records=json.loads((EVIDENCE/(base+'-192.168.17.2-packets.json')).read_text())
            groups=collections.defaultdict(dict)
            for r in records:groups[links[r['interface']]][r['seq']]=r['time']
            groups['DCA-Leaf01-uplinks']={**groups['vunl0_3_1'],**groups['vunl0_3_2']}
            spans=[]
            for a,b,kind in [('eth16','vunl0_9_4','bridge'),('vunl0_9_1','vunl0_6_2','bridge'),
                ('vunl0_6_10','eth5','bridge'),('eth3','vunl0_1_10','bridge'),
                ('vunl0_1_1','vunl0_3_1','bridge'),('vunl0_3_4','eth9','bridge'),
                ('eth4','vunl0_2_10','bridge'),('vunl0_2_1','vunl0_3_2','bridge'),
                ('vunl0_9_4','vunl0_9_1','DCB-Leaf02'),('DCA-Leaf01-uplinks','vunl0_3_4','DCA-Leaf01')]:
                if not groups[a]:continue
                values=sorted(1000*(groups[b][seq]-t) for seq,t in groups[a].items() if seq in groups[b])
                spans.append({'from':a,'to':b,'kind':kind,'matched':len(values),
                    'missing':len(set(groups[a])-set(groups[b])),
                    'median_ms':statistics.median(values) if values else None,
                    'p95_ms':values[int(len(values)*.95)] if values else None,
                    'max_ms':max(values) if values else None})
            test=json.loads((EVIDENCE/(base+'.json')).read_text())
            runs.append({'sent':test['sender']['sent'],'received':test['receiver']['received'],
                'loss_percent':100*(test['sender']['sent']-test['receiver']['received'])/test['sender']['sent'],
                'spans':spans,'start_epoch':min(r['time'] for r in records),
                'end_epoch':max(r['time'] for r in records),
                'capture_summaries':{h:c['capture_summary'] for h,c in test['captures'].items()}})
        sockets=collections.defaultdict(list)
        monitor=EVIDENCE/(label+'-socket-monitor.json')
        if monitor.exists():
            for s in json.loads(monitor.read_text()):
                for sock in s['sockets']:
                    interface = next((name for name in ['vmnicet1','vmnicet2','vmnicet5'] if ':'+name+' ' in sock),None)
                    if interface:
                        m=re.search(r'skmem:\(r(\d+),rb(\d+).*?,d(\d+)\)',sock)
                        sockets[interface].append({'time':s['time'],'receive_memory':int(m[1]),'limit':int(m[2]),'drops':int(m[3])})
        result[label]={'runs':runs,'sockets':{name:{'samples':len(items),
            'max_receive_memory':max(x['receive_memory'] for x in items),
            'limit':items[0]['limit'],'drop_delta':items[-1]['drops']-items[0]['drops']}
            for name,items in sockets.items()}}
    (EVIDENCE/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{'loss_percent':[x['loss_percent'] for x in v['runs']],
                        'sockets':v['sockets']} for k,v in result.items()},indent=2))


if __name__=='__main__':summarize()
