from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Plan, WorkOrder, AuditEvent, SchedulerState
from .scheduling import due_dates

def supervisor(user):
    return user.is_active and (user.is_superuser or user.groups.filter(name='Supervisor PM').exists())

def visible_orders(user):
    qs = WorkOrder.objects.select_related('plan__machine','assigned_to','submitted_by','approved_by')
    return qs if supervisor(user) else qs.filter(assigned_to=user)

def generate_orders(today=None):
    today = today or timezone.localdate()
    horizon = today + timedelta(days=7)
    count = 0
    ids = Plan.objects.filter(active=True,machine__active=True,next_due__lte=horizon).values_list('pk',flat=True)
    for pk in ids.iterator(chunk_size=100):
        with transaction.atomic():
            p = Plan.objects.select_for_update().get(pk=pk)
            if not p.active or not p.machine.active: continue
            dates, next_due = due_dates(p.next_due,horizon,p.interval_days)
            for due in dates:
                w, created = WorkOrder.objects.get_or_create(plan=p,due_date=due,defaults={'title':p.title,'checklist_snapshot':[s.strip() for s in p.checklist.splitlines() if s.strip()],'assigned_to':p.assigned_to})
                if created:
                    AuditEvent.objects.create(order=w,action='generated',detail={'due':str(due),'plan':p.pk})
                    count += 1
            if dates:
                p.next_due = next_due
                p.save(update_fields=['next_due'])
    SchedulerState.objects.update_or_create(name='pm',defaults={'last_ok':timezone.now(),'generated':count})
    return count

@transaction.atomic
def submit_order(pk,user,results,notes):
    w = WorkOrder.objects.select_for_update().get(pk=pk)
    if w.assigned_to_id != user.pk: raise PermissionDenied('Hanya teknisi yang ditugaskan dapat mengisi pekerjaan ini.')
    if w.status != 'open': raise ValidationError('Pekerjaan ini tidak sedang terbuka.')
    if not w.checklist_snapshot or len(results) != len(w.checklist_snapshot) or any(x not in ['ok','fail'] for x in results):
        raise ValidationError('Semua poin checklist harus dijawab.')
    notes = notes.strip()
    if len(notes)>4000: raise ValidationError('Catatan maksimal 4000 karakter.')
    if 'fail' in results and not notes: raise ValidationError('Temuan tidak normal harus disertai catatan tindak lanjut.')
    w.answers = [{'item':item,'result':result} for item,result in zip(w.checklist_snapshot,results)]
    w.notes = notes
    w.status = 'review'
    w.submitted_by = user
    w.submitted_at = timezone.now()
    w.save(update_fields=['answers','notes','status','submitted_by','submitted_at'])
    AuditEvent.objects.create(order=w,actor=user,action='submitted',detail={'answers':w.answers,'notes':notes})
    return w

@transaction.atomic
def review_order(pk,user,decision,note):
    if not supervisor(user): raise PermissionDenied('Verifikasi hanya untuk supervisor.')
    w = WorkOrder.objects.select_for_update().get(pk=pk)
    if w.status != 'review': raise ValidationError('Pekerjaan tidak sedang menunggu verifikasi.')
    if w.submitted_by_id == user.pk: raise ValidationError('Pemeriksa dan pemberi persetujuan harus berbeda.')
    if decision not in ['approve','reject']: raise ValidationError('Pilihan verifikasi tidak valid.')
    note = note.strip()
    if len(note)>2000: raise ValidationError('Catatan maksimal 2000 karakter.')
    if decision=='reject' and not note: raise ValidationError('Isi alasan pengembalian pekerjaan.')
    if decision=='approve':
        w.status='done'; w.approved_by=user; w.approved_at=timezone.now()
    else:
        w.status='open'
    w.save(update_fields=['status','approved_by','approved_at'])
    AuditEvent.objects.create(order=w,actor=user,action=decision,detail={'note':note})
    return w

@transaction.atomic
def assign_order(pk,user,technician):
    if not supervisor(user): raise PermissionDenied('Penugasan hanya untuk supervisor.')
    w=WorkOrder.objects.select_for_update().get(pk=pk)
    if w.status!='open': raise ValidationError('Hanya pekerjaan terbuka dapat dialihkan.')
    if not technician.is_active: raise ValidationError('Teknisi tidak aktif.')
    previous=w.assigned_to_id
    w.assigned_to=technician
    w.save(update_fields=['assigned_to'])
    AuditEvent.objects.create(order=w,actor=user,action='assigned',detail={'previous':previous,'assigned_to':technician.pk})
    return w
