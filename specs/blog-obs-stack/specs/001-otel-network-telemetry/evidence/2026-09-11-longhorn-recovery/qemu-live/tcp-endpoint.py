import socket,threading,time,json,struct,sys,hashlib
mode,local,peer,port,amount,rate,mss=sys.argv[1:];port,amount,rate,mss=map(int,[port,amount,rate,mss]);results={};errors=[]
listener=None
if mode=='server':
 listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.setsockopt(socket.IPPROTO_TCP,socket.TCP_MAXSEG,mss);listener.bind((local,port));listener.listen(1);listener.settimeout(60);print('READY',flush=True);s,_=listener.accept()
else:
 s=socket.socket();s.setsockopt(socket.IPPROTO_TCP,socket.TCP_MAXSEG,mss);s.settimeout(15);s.bind((local,0));s.connect((peer,port))
s.settimeout(30);s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);actual=s.getsockopt(socket.IPPROTO_TCP,socket.TCP_MAXSEG)
def send():
 try:
  start=time.monotonic();sent=0;h=hashlib.sha256()
  while sent<amount:
   data=b'q'*min(actual,amount-sent);s.sendall(data);h.update(data);sent+=len(data);delay=sent/rate-(time.monotonic()-start)
   if delay>0:time.sleep(delay)
  s.shutdown(socket.SHUT_WR);results.update(sent=sent,send_seconds=time.monotonic()-start,send_sha256=h.hexdigest())
 except Exception as e:errors.append('send: '+type(e).__name__+': '+str(e))
t=threading.Thread(target=send);t.start();start=time.monotonic();received=0;h=hashlib.sha256()
try:
 while True:
  b=s.recv(65536)
  if not b:break
  h.update(b);received+=len(b)
 results.update(received=received,receive_seconds=time.monotonic()-start,receive_sha256=h.hexdigest())
except Exception as e:errors.append('receive: '+type(e).__name__+': '+str(e))
t.join(timeout=30);info=s.getsockopt(socket.IPPROTO_TCP,socket.TCP_INFO,256)
results.update(mode=mode,local=local,peer=peer,requested_mss=mss,negotiated_mss=actual,total_retrans=struct.unpack_from('I',info,100)[0],errors=errors,ok=not errors and received==amount and results.get('sent')==amount and results.get('send_sha256')==results.get('receive_sha256'))
print(json.dumps(results),flush=True);s.close()
if listener:listener.close()
assert results['ok']
