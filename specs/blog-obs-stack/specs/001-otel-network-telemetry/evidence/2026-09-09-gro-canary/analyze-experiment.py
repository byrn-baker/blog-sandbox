import re,json,pathlib,statistics,collections,sys
root=pathlib.Path(sys.argv[1])
def packets(path):
 result=[]
 for b in re.split(r'(?=^\d{10}\.\d+ )',path.read_text(),flags=re.M):
  h=re.match(r'(\d+\.\d+) (\S+)\s+(\S+)',b)
  t=re.search(r'^\s+(192\.168\.100\.(?:11|30))\.(\d+) > (192\.168\.100\.(?:11|30))\.(\d+): (.*)$',b,re.M)
  if not h or not t:continue
  seq=re.search(r'\bseq (\d+):(\d+)',t[5]);length=re.search(r'\blength (\d+)$',t[5]);outer=re.search(r'proto UDP \(17\), length (\d+)',b)
  result.append({'t':float(h[1]),'iface':h[2],'dir':h[3],'server':t[1].endswith('.11'),'port':int(t[4] if t[1].endswith('.11') else t[2]),'seq':list(map(int,seq.groups())) if seq else None,'len':int(length[1]) if length else None,'outer':int(outer[1]) if outer else None,'tcp':t[5]})
 return result
reports={}
for phase in ['gro-off','restored']:
 d=root/phase
 if not (d/'probes.jsonl').exists():continue
 eve=packets(d/'eve.txt');master=packets(d/'master2.txt');worker=packets(d/'worker4.txt')
 rows=[]
 for probe in map(json.loads,(d/'probes.jsonl').read_text().splitlines()):
  port=probe['port'];path={}
  for leaf,iface in [('DCA-Leaf01','vunl0_3_5'),('DCA-Leaf02','vunl0_4_5')]:
   if any(x['port']==port and x['server'] and x['iface']==iface and x['dir']=='Out' for x in eve):path[leaf]=True
  oversized=[x for x in eve if x['port']==port and x['server'] and x['iface'] in ['vunl0_1_1','vunl0_1_2'] and x['dir']=='Out' and x['outer'] and x['outer']>1500]
  sent=[x for x in master if x['port']==port and x['server'] and x['iface']=='bond0' and x['seq']]
  seen=[];retrans=[]
  for x in sent:
   a,b=x['seq']
   if any(a<d and b>c for c,d in seen):retrans.append({'time':x['t'],'seq':x['seq'],'len':x['len']})
   seen.append((a,b))
  sack=sum(1 for x in worker if x['port']==port and not x['server'] and x['iface']=='bond0' and 'sack ' in x['tcp'])
  rows.append({**probe,'leaf':list(path),'total_s':float(probe['timing'].split()[-1]),'oversized':len(oversized),'oversized_lengths':[x['outer'] for x in oversized],'source_retransmissions':len(retrans),'source_data_packets':len(sent),'worker_sacks':sack})
 summary={}
 for leaf in ['DCA-Leaf01','DCA-Leaf02']:
  rs=[r for r in rows if r['leaf']==[leaf]]
  if rs:summary[leaf]={'connections':len(rs),'successes':sum(r['rc']==0 for r in rs),'median_s':round(statistics.median(r['total_s'] for r in rs),6),'min_s':min(r['total_s'] for r in rs),'max_s':max(r['total_s'] for r in rs),'oversized_packets':sum(r['oversized'] for r in rs),'source_retransmissions':sum(r['source_retransmissions'] for r in rs),'worker_sacks':sum(r['worker_sacks'] for r in rs),'source_data_packets':sum(r['source_data_packets'] for r in rs)}
 reports[phase]={'summary':summary,'connections':rows}
(root/'analysis.json').write_text(json.dumps(reports,indent=2)+'\n');print(json.dumps({k:v['summary'] for k,v in reports.items()},indent=2))
