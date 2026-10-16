import csv, io
from datetime import timedelta
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection, DatabaseError, IntegrityError, transaction
from django.db.models import Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from .models import Machine, Plan, SchedulerState
from .services import supervisor, visible_orders, submit_order, review_order, assign_order
from .forms import ChecklistForm, ReviewForm, ImportForm, AssignmentForm
from .machine_forms import MachineEditForm
from django.db.models.deletion import ProtectedError
from .importing import import_csv, import_excel, safe_cell, FIELDS
from .tabular import template_xlsx

def context(request,**kw):
    user = request.user
    return {'is_supervisor':supervisor(user),
            'can_add_machine':user.has_perm('maintenance.add_machine'),
            'can_edit_machine':user.has_perm('maintenance.change_machine'),
            'can_delete_machine':user.has_perm('maintenance.delete_machine'),
            'can_monitor_all':supervisor(user) or user.has_perm('inventory.approve_admin_request'), **kw}

def healthz(request):
    try:
        with connection.cursor() as c: c.execute('SELECT 1'); c.fetchone()
    except DatabaseError: return JsonResponse({'status':'database_unavailable'},status=503)
    return JsonResponse({'status':'ok','service':'multitek-pm','version':settings.APP_VERSION})

@login_required
def dashboard(request):
    today=timezone.localdate(); month=today.replace(day=1)
    qs=visible_orders(request.user)
    due=qs.filter(due_date__gte=month,due_date__lte=today)
    ontime=due.filter(status='done',submitted_at__date__lte=F('due_date')).count()
    total=due.count()
    heartbeat=SchedulerState.objects.filter(name='pm').first()
    return render(request,'dashboard.html',context(request,today=today,clock_epoch_ms=int(timezone.now().timestamp()*1000),machine_count=Machine.objects.filter(active=True).count(),plan_count=Plan.objects.filter(active=True).count(),open_count=qs.filter(status='open').count(),overdue_count=qs.exclude(status='done').filter(due_date__lt=today).count(),review_count=qs.filter(status='review').count(),done_month=qs.filter(status='done',approved_at__date__gte=month).count(),due_count=total,compliance=round(100*ontime/total,1) if total else None,heartbeat=heartbeat,scheduler_ok=bool(heartbeat and heartbeat.last_ok and heartbeat.last_ok>timezone.now()-timedelta(minutes=15)),recent=qs.exclude(status='done')[:10]))

@login_required
def machines(request):
    qs=Machine.objects.all(); q=request.GET.get('q','').strip()[:100]
    if q: qs=qs.filter(Q(code__icontains=q)|Q(name__icontains=q)|Q(site__icontains=q)|Q(line__icontains=q)|Q(serial__icontains=q))
    return render(request,'machines.html',context(request,page=Paginator(qs,50).get_page(request.GET.get('page')),q=q))

@login_required
def machine_detail(request,uid):
    m=get_object_or_404(Machine,uid=uid)
    return render(request,'machine.html',context(request,machine=m,plans=m.plans.select_related('assigned_to'),history=visible_orders(request.user).filter(plan__machine=m)[:30],qr_enabled=bool(settings.PUBLIC_BASE_URL)))

@login_required
@require_GET
def machine_qr(request,uid):
    m=get_object_or_404(Machine,uid=uid)
    if not settings.PUBLIC_BASE_URL:
        return HttpResponse('QR tautan belum aktif: tentukan hostname HTTPS final lebih dahulu.',status=409)
    parsed=urlsplit(settings.PUBLIC_BASE_URL)
    if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.query or parsed.fragment or parsed.path not in ('','/'):
        return HttpResponse('PM_PUBLIC_BASE_URL harus origin HTTPS tanpa path.',status=409)
    import qrcode
    import qrcode.image.svg
    img=qrcode.make(settings.PUBLIC_BASE_URL+reverse('machine_detail',args=[m.uid]),image_factory=qrcode.image.svg.SvgPathImage,box_size=8,border=4)
    data=io.BytesIO(); img.save(data)
    response=HttpResponse(data.getvalue(),content_type='image/svg+xml')
    response['Content-Disposition']=f'inline; filename="machine-{m.uid}.svg"'
    return response

@login_required
def orders(request):
    qs=visible_orders(request.user); status=request.GET.get('status',''); q=request.GET.get('q','').strip()[:100]
    if status=='overdue': qs=qs.exclude(status='done').filter(due_date__lt=timezone.localdate())
    elif status in ['open','review','done']: qs=qs.filter(status=status)
    if q: qs=qs.filter(Q(plan__machine__code__icontains=q)|Q(title__icontains=q)|Q(plan__machine__site__icontains=q))
    return render(request,'orders.html',context(request,page=Paginator(qs,50).get_page(request.GET.get('page')),q=q,status=status))

@login_required
def order_detail(request,pk):
    w=get_object_or_404(visible_orders(request.user),pk=pk)
    can_submit=w.status=='open' and w.assigned_to_id==request.user.pk
    can_review=w.status=='review' and supervisor(request.user) and w.submitted_by_id!=request.user.pk
    form=ChecklistForm(items=w.checklist_snapshot)
    review=ReviewForm()
    assign_form=AssignmentForm(initial={'technician':w.assigned_to_id}) if supervisor(request.user) and w.status=='open' else None
    if request.method=='POST':
        try:
            if request.POST.get('action')=='submit':
                if not can_submit: raise PermissionDenied
                form=ChecklistForm(request.POST,items=w.checklist_snapshot)
                if form.is_valid():
                    submit_order(w.pk,request.user,[form.cleaned_data[f'item_{i}'] for i in range(len(w.checklist_snapshot))],form.cleaned_data['notes'])
                    messages.success(request,'Hasil dikirim. Menunggu verifikasi supervisor yang berbeda.')
                    return redirect('order_detail',pk=w.pk)
            elif request.POST.get('action')=='review':
                if not can_review: raise PermissionDenied
                review=ReviewForm(request.POST)
                if review.is_valid():
                    review_order(w.pk,request.user,review.cleaned_data['decision'],review.cleaned_data['note'])
                    messages.success(request,'Keputusan supervisor tersimpan.')
                    return redirect('order_detail',pk=w.pk)
            elif request.POST.get('action')=='assign':
                if assign_form is None: raise PermissionDenied
                assign_form=AssignmentForm(request.POST)
                if assign_form.is_valid():
                    assign_order(w.pk,request.user,assign_form.cleaned_data['technician'])
                    messages.success(request,'Penugasan work order disimpan. Jadwal masa depan tetap mengikuti master jadwal.')
                    return redirect('order_detail',pk=w.pk)
            else: raise PermissionDenied
        except ValidationError as exc: messages.error(request,'; '.join(exc.messages))
    return render(request,'order.html',context(request,order=w,form=form,review=review,can_submit=can_submit,can_review=can_review,assign_form=assign_form,events=w.events.select_related('actor')[:30]))

@login_required
def import_machines(request):
    if not request.user.has_perm('maintenance.add_machine'): raise PermissionDenied
    form=ImportForm(request.POST or None,request.FILES or None)
    if request.method=='POST' and form.is_valid():
        try:
            upload=form.cleaned_data['file']
            if upload.name.lower().endswith('.xlsx'):
                count=import_excel(upload.read(5*1024*1024+1),request.user,form.cleaned_data.get('sheet_name',''))
            else:
                count=import_csv(upload.read(2*1024*1024+1),request.user)
            messages.success(request,f'{count} mesin berhasil ditambahkan. Data lama tidak ditimpa.')
            return redirect('machines')
        except (ValidationError,IntegrityError,csv.Error) as exc:
            messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'File tidak valid atau kode mesin berbenturan. Tidak ada data impor yang disimpan.')
    return render(request,'import.html',context(request,form=form))

@login_required
@require_GET
def machine_template(request):
    response=HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="template-mesin.csv"'
    response.write('\ufeff'); csv.writer(response).writerow(FIELDS)
    return response

@login_required
@require_GET
def export_orders(request):
    if not (supervisor(request.user) or request.user.has_perm('inventory.approve_admin_request')):
        raise PermissionDenied
    qs=visible_orders(request.user)
    status=request.GET.get('status','')
    q=request.GET.get('q','').strip()[:100]
    if status=='overdue':qs=qs.exclude(status='done').filter(due_date__lt=timezone.localdate())
    elif status in ('open','review','done'):qs=qs.filter(status=status)
    if q:qs=qs.filter(Q(plan__machine__code__icontains=q)|Q(title__icontains=q)|Q(plan__machine__site__icontains=q))
    response=HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']='attachment; filename="multitek-pm-workorders.csv"'
    response['Cache-Control']='private, no-store'
    response['X-Export-Limit']='20000'
    response.write('\ufeff');writer=csv.writer(response)
    writer.writerow(['id','mesin','pabrik','line','pekerjaan','jatuh_tempo','status','teknisi','dikirim','disetujui','catatan'])
    for w in qs.order_by('-due_date','-id')[:20000].iterator(chunk_size=250):
        writer.writerow([safe_cell(x) for x in [w.pk,w.plan.machine.code,w.plan.machine.site,w.plan.machine.line,
                     w.title,w.due_date,w.get_status_display(),w.assigned_to or '',w.submitted_at or '',w.approved_at or '',w.notes]])
    return response


@login_required
@require_GET
def machine_template_excel(request):
    if not request.user.has_perm('maintenance.add_machine'): raise PermissionDenied
    response=HttpResponse(template_xlsx(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']='attachment; filename="template-mesin-multitek.xlsx"'
    response['Cache-Control']='private, no-store'
    return response

@login_required
@require_GET
def server_time(request):
    response=JsonResponse({'epoch_ms':int(timezone.now().timestamp()*1000),'timezone':'Asia/Jakarta'})
    response['Cache-Control']='private, no-store, max-age=0'
    return response


@login_required
@permission_required('maintenance.add_machine', raise_exception=True)
def machine_add(request):
    form = MachineEditForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                machine=form.save()
                from inventory.services import _audit
                _audit('machine',machine.pk,'created',request.user,after={'code':machine.code,'name':machine.name,'site':machine.site,'line':machine.line})
            messages.success(request, 'Mesin berhasil ditambahkan.')
            return redirect('machine_detail', uid=machine.uid)
        except IntegrityError:
            form.add_error('code','Kode mesin sudah digunakan.')
    return render(request,'machine_form.html',context(request,form=form,title='Tambah mesin',submit_label='Simpan mesin'))


@login_required
@permission_required('maintenance.change_machine', raise_exception=True)
def machine_edit(request, uid):
    machine=get_object_or_404(Machine,uid=uid)
    form=MachineEditForm(request.POST or None,instance=machine)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=Machine.objects.select_for_update().get(pk=machine.pk)
                old={'code':locked.code,'name':locked.name,'site':locked.site,'line':locked.line,'serial':locked.serial,'active':locked.active}
                form.save()
                from inventory.services import _audit
                new={'code':machine.code,'name':machine.name,'site':machine.site,'line':machine.line,'serial':machine.serial,'active':machine.active}
                if old!=new:_audit('machine',machine.pk,'edited',request.user,before=old,after=new)
            messages.success(request,'Master mesin berhasil diperbarui.')
            return redirect('machine_detail',uid=machine.uid)
        except IntegrityError:
            form.add_error('code','Kode mesin sudah digunakan.')
    return render(request,'machine_form.html',context(request,form=form,title='Ubah mesin',submit_label='Simpan perubahan'))


@login_required
@permission_required('maintenance.delete_machine', raise_exception=True)
def machine_delete(request, uid):
    machine=get_object_or_404(Machine,uid=uid)
    if request.method=='POST':
        if request.POST.get('confirmation')!=machine.code:
            messages.error(request,'Ketik kode mesin secara tepat untuk konfirmasi penghapusan.')
        else:
            try:
                with transaction.atomic():
                    before={'code':machine.code,'name':machine.name,'serial':machine.serial}
                    pk=machine.pk
                    machine.delete()
                    from inventory.services import _audit
                    _audit('machine',pk,'deleted',request.user,before=before)
                messages.success(request,'Master mesin berhasil dihapus.')
                return redirect('machines')
            except ProtectedError:
                messages.error(request,'Mesin memiliki jadwal/riwayat terkait. Nonaktifkan melalui Ubah mesin; riwayat tidak dihapus.')
    return render(request,'machine_delete.html',context(request,machine=machine))
