import pathlib,struct,socket,collections,json
root=pathlib.Path('/home/ubuntu/cml-qemu-live/capture-gro-off-pinned')
def csum(b):
 if len(b)%2:b+=b'\0'
 s=sum(struct.unpack('!'+str(len(b)//2)+'H',b));s=(s&65535)+(s>>16);s=(s&65535)+(s>>16);return (~s)&65535
def parse(b,proto,offset):
 while proto in [0x8100,0x88a8]:proto=struct.unpack_from('!H',b,offset+2)[0];offset+=4
 if proto!=0x0800:return None
 ip=b[offset:];ihl=(ip[0]&15)*4;total=struct.unpack_from('!H',ip,2)[0];p=ip[9];src=socket.inet_ntoa(ip[12:16]);dst=socket.inet_ntoa(ip[16:20]);tun=False
 if p==17:
  udp=ip[ihl:]
  if len(udp)<40 or struct.unpack_from('!H',udp,2)[0]!=4789:return None
  eth=udp[16:];proto=struct.unpack_from('!H',eth,12)[0];inner=parse(eth,proto,14)
  if inner:inner.update(tunnel=True,outer_src=src,outer_dst=dst)
  return inner
 if p!=6:return None
 tcp=ip[ihl:];sport,dport,seq,ack=struct.unpack_from('!HHII',tcp);hlen=(tcp[12]>>4)*4;length=total-ihl-hlen
 if 49492 not in [sport,dport] or length<0:return None
 header=tcp[:hlen];data=tcp[hlen:]
 known=not length or all(v==113 for v in data)
 valid=None
 if known and len(header)==hlen:
  pseudo=ip[12:20]+b'\0\x06'+struct.pack('!H',total-ihl);valid=csum(pseudo+header+b'q'*length)==0
 return {'src':src,'dst':dst,'sport':sport,'dport':dport,'seq':seq,'ack':ack,'len':length,'flags':tcp[13],'checksum_valid_reconstructed':valid,'tunnel':tun}
allrows=[]
for p in root.glob('*.pcap'):
 b=p.read_bytes();pos=24
 while pos+16<=len(b):
  sec,usec,cap,orig=struct.unpack_from('<IIII',b,pos);pos+=16;packet=b[pos:pos+cap];pos+=cap
  if len(packet)<40:continue
  try:r=parse(packet,struct.unpack_from('!H',packet)[0],20)
  except (struct.error,IndexError):continue
  if r:r.update(host=p.stem,time=sec+usec/1e6,ifindex=struct.unpack_from('!I',packet,4)[0],pkttype=packet[10],origlen=orig);allrows.append(r)
(root/'parsed.json').write_text(json.dumps(allrows))
summary=collections.defaultdict(collections.Counter)
for r in allrows:
 if r['len']:summary[(r['host'],r['ifindex'],r['pkttype'],r['tunnel'],r['src'])][('good' if r['checksum_valid_reconstructed'] else 'bad',r['len'])]+=1
for k,v in sorted(summary.items()):print(k,dict(v))
