import os,fcntl,struct,socket,select,sys
name,listen,dest=sys.argv[1],int(sys.argv[2]),int(sys.argv[3])
fd=os.open('/dev/net/tun',os.O_RDWR|os.O_NONBLOCK)
fcntl.ioctl(fd,0x400454ca,struct.pack('16sH',name.encode(),0x0002|0x1000))
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(('127.0.0.1',listen));s.setblocking(False)
while True:
 for item in select.select([fd,s],[],[])[0]:
  if item==fd:s.sendto(os.read(fd,65535),('127.0.0.1',dest))
  else:
   data,_=s.recvfrom(65535);os.write(fd,data)
