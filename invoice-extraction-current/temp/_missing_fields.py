import json, glob, os
files = sorted(glob.glob(r'invoice-extraction-current/outputs/extractions/*.json'))
missing_vendor=[]
missing_billto=[]
missing_inv=[]
for p in files:
    with open(p,'r',encoding='utf-8') as f:
        d=json.load(f)
    name=os.path.basename(p)
    if not ((d.get('vendor') or {}).get('name')):
        missing_vendor.append(name)
    if not ((d.get('bill_to') or {}).get('name')):
        missing_billto.append(name)
    if not d.get('invoice_number'):
        missing_inv.append(name)
print('missing_vendor_files=', len(missing_vendor))
for x in missing_vendor[:20]: print(' -', x)
print('missing_bill_to_files=', len(missing_billto))
for x in missing_billto[:20]: print(' -', x)
print('missing_invoice_number_files=', len(missing_inv))
for x in missing_inv[:40]: print(' -', x)
