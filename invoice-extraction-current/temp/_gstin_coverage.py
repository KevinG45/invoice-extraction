import json, glob, os, re
files=sorted(glob.glob(r'invoice-extraction-current/outputs/extractions/*.json'))
vm=0; bm=0; invalid_v=0; invalid_b=0
v_missing=[]; b_missing=[]; bad_v=[]; bad_b=[]
pat=re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]{2}$')
for p in files:
    d=json.load(open(p,'r',encoding='utf-8'))
    name=os.path.basename(p)
    v=((d.get('vendor') or {}).get('tax_id') or '').strip()
    b=((d.get('bill_to') or {}).get('tax_id') or '').strip()
    if not v:
        vm+=1; v_missing.append(name)
    elif not pat.match(v):
        invalid_v+=1; bad_v.append((name,v))
    if not b:
        bm+=1; b_missing.append(name)
    elif not pat.match(b):
        invalid_b+=1; bad_b.append((name,b))
print(f'total={len(files)}')
print(f'vendor_gstin_missing={vm}')
print(f'vendor_gstin_invalid={invalid_v}')
print(f'billto_gstin_missing={bm}')
print(f'billto_gstin_invalid={invalid_b}')
print('sample_vendor_missing=', v_missing[:10])
print('sample_billto_missing=', b_missing[:10])
print('sample_vendor_invalid=', bad_v[:8])
print('sample_billto_invalid=', bad_b[:8])
