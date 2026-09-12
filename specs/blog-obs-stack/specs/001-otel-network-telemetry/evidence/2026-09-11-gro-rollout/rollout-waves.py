import subprocess,sys,time,json,pathlib
root=pathlib.Path('/home/ubuntu/gro-rollout')
canary=json.loads((root/'DCA-Leaf01-verified.json').read_text());assert canary['ok']
for wave,names in enumerate([['DCA-Leaf02','DCB-Leaf01','DCB-Leaf02','DCC-Leaf01'],['DCA-Leaf03','DCB-Leaf03','DCC-Leaf02','DCC-Leaf03']],1):
 print('WAVE',wave,names,flush=True)
 subprocess.run([sys.executable,str(root/'deploy.py'),*names],check=True)
 time.sleep(60)
 subprocess.run([sys.executable,str(root/'verify.py'),*names],check=True)
 print('WAVE_VERIFIED',wave,flush=True)
