import pathlib,subprocess,json
src=pathlib.Path('/tmp/validate-lab-mtu.py').read_text(); code=src.split("code=r'''",1)[1].split("'''",1)[0]
code=code.replace("names=list(Device.objects.filter(role__name__in=['Border-Router','CE-Router','P-Router','PE-Router','Route-Reflector','Leaf','Spine']).values_list('name',flat=True))", "names=['DCA-Leaf01','DCB-Leaf01','DCC-Leaf01']")
a=code.index("   commands=['show interfaces'");b=code.index("   row['commands']={}",a)
code=code[:a]+'''   if eos:
    source={'DCA-Leaf01':'10.3.1.4','DCB-Leaf01':'10.3.2.4','DCC-Leaf01':'10.3.3.4'}[name]
    targets=[t for t in ['10.3.1.4','10.3.2.4','10.3.3.4'] if t!=source]
    commands=['bash sudo -n ip netns exec default ip -o address show','show ip route 10.3.3.4' if name=='DCA-Leaf01' else 'show ip route 10.3.1.4']
    for target in targets:
     for size in [1422,1464,1465]:
      commands.append('bash sudo -n ip netns exec default ping -n -I '+source+' -M do -c 3 -W 2 -s '+str(size)+' '+target)
   else:commands=['show interfaces','show ip interface brief','show mpls interfaces detail']
'''+code[b:]
p=subprocess.run(['docker','exec','nautobot_docker_compose-nautobot-1','nautobot-server','shell','--interface','python','--command',code],capture_output=True,text=True)
out=pathlib.Path('/tmp/mtu-validation-20260910T011701Z')
for line in p.stdout.splitlines():
 if line.startswith('{'):
  d=json.loads(line)
  if 'device' in d:
   (out/(d['device']+'-boundary.json')).write_text(json.dumps(d,indent=2));print(json.dumps(d),flush=True)
print('returncode',p.returncode)
