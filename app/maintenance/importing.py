import csv, io
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Machine, AuditEvent
from .tabular import FIELDS, read_xlsx, ImportFileError

def safe_cell(value):
    text=str(value or '')
    if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')):
        return "'"+text
    return text

@transaction.atomic
def save_machine_rows(rows, actor, source_format='csv', sheet=''):
    objects=[]; seen=set()
    for n,row in rows:
        if len(objects) >= 5000:
            raise ValidationError('Maksimal 5.000 mesin per impor.')
        obj=Machine(**{f:str(row.get(f,'')).strip() for f in FIELDS})
        if obj.code in seen:
            raise ValidationError(f'Kode berulang pada baris {n}: {obj.code}')
        try: obj.full_clean(validate_unique=False,validate_constraints=False)
        except ValidationError as exc: raise ValidationError(f'Baris {n}: '+'; '.join(exc.messages))
        seen.add(obj.code); objects.append(obj)
    if not objects: raise ValidationError('File tidak berisi data mesin.')
    # Chunk queries for SQLite development as well as PostgreSQL production.
    existing=[]; codes=list(seen)
    for start in range(0,len(codes),400):
        existing.extend(Machine.objects.filter(code__in=codes[start:start+400]).values_list('code',flat=True)[:5])
        if existing: break
    if existing:
        raise ValidationError('Kode sudah ada. Impor dibatalkan tanpa menimpa: '+', '.join(existing[:5]))
    Machine.objects.bulk_create(objects,batch_size=250)
    AuditEvent.objects.create(actor=actor,action='machine_import',detail={'count':len(objects),'format':source_format,'sheet':sheet})
    return len(objects)

def import_csv(data,actor):
    if len(data)>2*1024*1024: raise ValidationError('Ukuran CSV maksimal 2 MiB.')
    try: text=data.decode('utf-8-sig')
    except UnicodeDecodeError: raise ValidationError('File harus CSV dengan encoding UTF-8.')
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or any(f not in reader.fieldnames for f in FIELDS) or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValidationError('Header harus sesuai template CSV yang disediakan (pemisah koma).')
    rows=[]
    for n,row in enumerate(reader,start=2):
        if n>5001: raise ValidationError('Maksimal 5.000 mesin per impor.')
        if None in row or any(row.get(f) is None for f in FIELDS):
            raise ValidationError(f'Kolom tidak lengkap pada baris {n}.')
        rows.append((n,{f:row[f].strip() for f in FIELDS}))
    return save_machine_rows(rows,actor)

def import_excel(data,actor,sheet_name=''):
    try: sheet, rows=read_xlsx(data,sheet_name)
    except ImportFileError as exc: raise ValidationError(str(exc)) from exc
    return save_machine_rows(rows,actor,'xlsx',sheet)
