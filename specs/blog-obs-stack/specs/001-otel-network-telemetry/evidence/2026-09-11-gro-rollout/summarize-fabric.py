import pathlib,json,re
root=pathlib.Path('/home/ubuntu/gro-rollout');rows=[]
for p in sorted((root/'fabric').glob('*.json')):
 r=json.loads(p.read_text());row={'device':r['name'],'ok':r['ok'],'isis_up':0,'bgp':{}};assert r['ok'],r['name']
 for command,out in r['commands'].items():
  if command=='show isis neighbors':
   lines=[l.split() for l in out.splitlines() if re.search(r'\sL2\s',l)];row['isis_up']=sum('UP' in l for l in lines);row['isis_other']=[l for l in lines if 'UP' not in l]
  if command in ['show ip bgp summary','show ip bgp vpnv4 all summary','show bgp evpn summary']:
   peers=[]
   for line in out.splitlines():
    tokens=line.split();indices=[i for i,t in enumerate(tokens) if re.fullmatch(r'\d+\.\d+\.\d+\.\d+',t)]
    if not indices:continue
    i=indices[0]
    if len(tokens)<=i+3 or not tokens[i+1].isdigit() or not tokens[i+2].isdigit():continue
    state=tokens[i+8] if 'PfxAcc' in out and len(tokens)>i+8 else tokens[-1]
    peers.append({'peer':tokens[i],'state':state,'up':state=='Estab' or state.isdigit()})
   row['bgp'][command]={'up':sum(x['up'] for x in peers),'total':len(peers),'other':[x for x in peers if not x['up']]}
  if 'show interfaces' in command:
   row['mtus']=sorted(set(re.findall(r'MTU (\d+)',out)))
 rows.append(row)
(root/'fabric-summary.json').write_text(json.dumps(rows,indent=2))
print(json.dumps({'devices':len(rows),'isis_directed_up':sum(r['isis_up'] for r in rows),'isis_other':{r['device']:r['isis_other'] for r in rows if r.get('isis_other')},'bgp_non_established':{r['device']:{k:v for k,v in r['bgp'].items() if v['other']} for r in rows if any(v['other'] for v in r['bgp'].values())}},indent=2))
assert len(rows)==28 and sum(r['isis_up'] for r in rows)==28
