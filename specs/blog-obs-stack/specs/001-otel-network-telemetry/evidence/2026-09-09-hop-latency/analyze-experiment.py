import re,json,collections,statistics,pathlib
root=pathlib.Path('/tmp/lab-latency-20260909/hop-trace-repeat')
text=(root/'eve.txt').read_text();packets=[]
for b in re.split(r'(?=^\d{10}\.\d+ )',text,flags=re.M):
 h=re.match(r'(\d+\.\d+) (\S+)\s+(\S+)',b)
 if not h:continue
 tcp=re.findall(r'^\s+(192\.168\.100\.(?:11|30)\.\d+ > 192\.168\.100\.(?:11|30)\.\d+: Flags .*)$',b,re.M)
 if not tcp:continue
 key=re.sub(r', cksum .*?, seq',', seq',tcp[-1])
 key=re.sub(r', cksum .*?, ack',', ack',key)
 packets.append({'time':float(h[1]),'if':h[2],'direction':h[3],'key':key})
bykey=collections.defaultdict(list)
for p in packets:bykey[p['key']].append(p)
node_names={n['cwd'].split('/')[-1]:n['-name'] for n in json.load(open('/tmp/lab-latency-20260909/discovery-118.json'))['nodes']}
spans=collections.defaultdict(list);examples=[]
for key,ps in bykey.items():
 pending={};external=None
 for p in ps:
  m=re.match(r'vunl0_(\d+)_\d+',p['if'])
  if m:
   n=node_names.get(m[1],m[1])
   if p['direction']=='Out':pending[n]=p
   elif p['direction'] in ['P','In'] and n in pending:
    old=pending.pop(n);dt=1000*(p['time']-old['time']);spans[n].append(dt)
    examples.append({'node':n,'ms':round(dt,3),'in':old['if'],'out':p['if'],'key':key})
  if p['if'] in ['eth3','eth4','eth7','eth8']:
   if p['direction']=='Out':external=p
   elif external and p['if']!=external['if']:
    spans['CML + PVE handoffs'].append(1000*(p['time']-external['time']));external=None
summary={k:{'n':len(v),'min_ms':round(min(v),3),'median_ms':round(statistics.median(v),3),'p95_ms':round(sorted(v)[int(.95*(len(v)-1))],3),'max_ms':round(max(v),3)} for k,v in spans.items()}
(root/'hop-analysis.json').write_text(json.dumps({'summary':summary,'spans':examples},indent=2))
print(json.dumps(summary,indent=2))
print('SYN first path')
for p in packets:
 if '.48100 >' in p['key'] and 'Flags [S],' in p['key']:print(p['time'],p['if'],p['direction'])
