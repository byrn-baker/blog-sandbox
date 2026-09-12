import subprocess,sys,pathlib
p=pathlib.Path('/home/ubuntu/cml-qemu-live')
def run(name,*args):
 subprocess.run([sys.executable,str(p/name),*args],check=True)
try:
 run('gro-canary.py','apply')
 run('capture-gro-pinned.py')
finally:
 run('gro-canary.py','restore')
