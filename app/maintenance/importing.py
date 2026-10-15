import csv, io
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Machine, AuditEvent
FIELDS=['code','name','category','manufacturer','model','serial','site','line']

def safe_cell(value):
    text=str(value or '')
    if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')):
        return "'"+text
    return text

@transaction.atomic
def import_csv(data,actor):
    if len(data)>2*1024*1024: raise ValidationError('Ukuran maksimal 2 MB.')
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValidationError('File harus CSV dengan encoding UTF-8.')
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or any(f not in reader.fieldnames for f in FIELDS):
        raise ValidationError('Header harus sesuai template CSV yang disediakan (pemisah koma).')
    objects=[]; seen=set()
    for n,row in enumerate(reader,start=2):
        if n>5001: raise ValidationError('Maksimal 5.000 mesin per impor.')
        if None in row or any(row.get(f) is None for f in FIELDS): raise ValidationError(f'Kolom tidak lengkap pada baris {n}.')
        obj=Machine(**{f:row[f].strip() for f in FIELDS})
        if obj.code in seen: raise ValidationError(f'Kode berulang dalam CSV pada baris {n}: {obj.code}')
        try: obj.full_clean(validate_unique=False,validate_constraints=False)
        except ValidationError as exc: raise ValidationError(f'Baris {n}: '+ '; '.join(exc.messages))
        seen.add(obj.code); objects.append(obj)
    if not objects: raise ValidationError('CSV kosong.')
    existing=list(Machine.objects.filter(code__in=seen).values_list('code',flat=True)[:5])
    if existing: raise ValidationError('Kode sudah ada. Impor dibatalkan tanpa menimpa: '+', '.join(existing))
    Machine.objects.bulk_create(objects,batch_size=250)
    AuditEvent.objects.create(actor=actor,action='machine_import',detail={'count':len(objects)})
    return len(objects)
