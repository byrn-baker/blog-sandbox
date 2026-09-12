import pathlib,json,re,sys
root=pathlib.Path('/home/ubuntu/cml-qemu-live');expected={'RR1':1,'RR2':1,'SP1':5,'SP2':5,'SP3':4,'SP4':4,'SPE1':2,'SPE2':2,'SPE3':2,'BORDER1':2}
for name in sys.argv[1:]:
 r=json.loads((root/(name+'-verify.json')).read_text());assert r['ok'] and r['configuration_preserved'];commands=r['commands']
 if name in expected:
  rows=[l.split() for l in commands['show isis neighbors'].splitlines() if re.search(r'\sL2\s',l)];up=[x for x in rows if 'UP' in x];assert len(up)==expected[name] and len(rows)==len(up),(name,'IS-IS',rows)
  print(json.dumps({'device':name,'isis_up':len(up)}))
 if name.startswith('CE'):
  rows=[l.split() for l in commands['show ip bgp summary'].splitlines() if re.match(r'^\d+\.\d+\.\d+\.\d+\s',l)];up=[x for x in rows if x[-1].isdigit()]
  baseline=json.loads((root/(name+'-baseline.json')).read_text());prior=[l.split() for l in baseline['commands']['show ip bgp summary'].splitlines() if re.match(r'^\d+\.\d+\.\d+\.\d+\s',l) and l.split()[-1].isdigit()]
  assert len(up)>=len(prior),(name,'BGP below baseline',rows)
  print(json.dumps({'device':name,'bgp_up':len(up),'bgp_total':len(rows)}))
