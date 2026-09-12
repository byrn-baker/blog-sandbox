import json

def scan(last, shadow, actual, required, narrow):
    idx=last; total=0; reads=0; steps=0
    while steps<257:
        compare_idx=(idx & 65535) if narrow else idx
        if shadow==compare_idx:
            shadow=actual; reads+=1
        heads=(shadow-idx)&65535
        if heads==0:break
        if heads>256:raise ValueError('invalid head count')
        total+=2060; idx+=1;steps+=1
        if total>=required:break
    return dict(bytes_found=total,sufficient=total>=required,guest_index_reads=reads,descriptors=steps)
rows=[]
for name,last,shadow,actual in [('SPE3-Gi2',65535,1,255),('SPE3-Gi3',65533,0,253),('nonwrap',100,102,356)]:
    for size in [1212,9241]:
        row=dict(case=name,last=last,shadow=shadow,actual=actual,required=size,original=scan(last,shadow,actual,size,False),narrowed_comparison=scan(last,shadow,actual,size,True))
        rows.append(row)
assert all(x['original']['sufficient'] for x in rows if x['required']==1212)
assert all(not x['original']['sufficient'] for x in rows if x['required']==9241 and x['case']!='nonwrap')
assert all(x['narrowed_comparison']['sufficient'] for x in rows)
print(json.dumps({'scope':'Local arithmetic model of QEMU 8.2.2 split-ring availability scan, not a patched-QEMU integration test','results':rows},indent=2))
