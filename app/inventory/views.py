"""Mobile-friendly pages. Every stock write uses inventory.services transactions."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Count
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from maintenance.services import visible_orders
from .forms import PartForm, MovementForm, RequestForm, DecisionForm, StocktakeForm, CountForm
from .models import Part, PartRequest, StockMovement, Stocktake, StocktakeLine, StockImportBatch, ManualStockRequest, InventoryAudit
from .services import (can_manage, can_monitor, move_stock, make_request, review_request,
                       fulfill_request, cancel_request, return_issued, start_stocktake, count_line,
                       post_stocktake, cancel_stocktake, is_stock_admin, is_sparepart_manager,
                       can_approve_request, import_stock_rows, review_import,
                       propose_manual, review_manual, _audit, _snapshot_part)
from .importing import parse_uploaded, HEADERS


def page_context(request, **kwargs):
    return {'can_manage_stock': can_manage(request.user), 'can_review_admin': is_sparepart_manager(request.user),
            'can_request_parts': not (is_sparepart_manager(request.user) and not is_stock_admin(request.user)),
            'can_monitor_stock': can_monitor(request.user), **kwargs}


def active_user(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_active:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def _show_error(request, error):
    text = '; '.join(error.messages) if isinstance(error, ValidationError) else str(error)
    messages.error(request, text[:300])


@active_user
@require_GET
def overview(request):
    q = request.GET.get('q', '').strip()[:100]
    parts = Part.objects.filter(active=True)
    if q:
        parts = parts.filter(Q(sku__icontains=q)|Q(name__icontains=q)|Q(machine_type__icontains=q)|Q(location__icontains=q))
    low = Part.objects.filter(active=True, current_qty__lte=F('min_qty'))
    pending = PartRequest.objects.filter(status='pending')
    if not request.user.is_superuser:
        visibility = Q(requested_by=request.user)
        if is_stock_admin(request.user):
            visibility |= Q(approval_route='stock_admin')
        if is_sparepart_manager(request.user):
            visibility |= Q(approval_route='manager')
        pending = pending.filter(visibility)
    return render(request, 'inventory/overview.html', page_context(
        request, page=Paginator(parts.order_by('sku'), 40).get_page(request.GET.get('page')),
        q=q, total=Part.objects.filter(active=True).count(), low_count=low.count(),
        pending_count=pending.count(), low=low.order_by('current_qty', 'sku')[:8],
        recent=StockMovement.objects.select_related('part', 'actor')[:8] if can_monitor(request.user) else []))


@active_user
def add_part(request):
    if not can_manage(request.user):
        raise PermissionDenied
    form = PartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                part = form.save()
                _audit('part',part.pk,'created',request.user,after=_snapshot_part(part))
            messages.success(request, f'Sparepart {part.sku} dibuat. Stok awal nol; catat penerimaan barang.')
            return redirect('inventory_overview')
        except IntegrityError:
            form.add_error('sku', 'Kode sudah digunakan.')
    return render(request, 'inventory/form.html', page_context(
        request, form=form, title='Tambah master sparepart', subtitle='Stok awal nol. Stok berubah melalui mutasi atau opname.',
        submit_label='Simpan sparepart', back_url='inventory_overview'))


@active_user
def edit_part(request, pk):
    if not can_manage(request.user):raise PermissionDenied
    part=get_object_or_404(Part,pk=pk)
    form=PartForm(request.POST or None, instance=part)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                locked=Part.objects.select_for_update().get(pk=pk)
                if locked.unit!=form.cleaned_data['unit'] and StockMovement.objects.filter(part=locked).exists():
                    raise ValidationError('Satuan tidak boleh diganti setelah ada mutasi; buat SKU baru atau rekonsiliasi resmi.')
                old=_snapshot_part(locked)
                fields=('sku','name','machine_type','unit','location','min_qty','active')
                values={f:form.cleaned_data[f] for f in fields}
                from django.utils import timezone
                Part.objects.filter(pk=locked.pk).update(**values,updated_at=timezone.now())
                locked.refresh_from_db()
                new=_snapshot_part(locked)
                if old!=new:_audit('part',pk,'edited',request.user,before=old,after=new)
            messages.success(request,'Master diperbarui; saldo dan riwayat mutasi tidak berubah.')
            return redirect('inventory_overview')
        except IntegrityError:form.add_error('sku','Kode sudah digunakan.')
        except ValidationError as exc:form.add_error(None,exc)
    return render(request, 'inventory/form.html', page_context(
        request, form=form, title='Ubah master sparepart',
        subtitle='Edit master tidak pernah menulis ulang saldo. Perubahan satuan dengan riwayat transaksi ditolak.',
        submit_label='Simpan perubahan', back_url='inventory_overview'))


@active_user
def movement(request):
    if not can_manage(request.user):raise PermissionDenied
    form=MovementForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            d=form.cleaned_data
            proposal=propose_manual(d['part'].pk,d['kind'],d['quantity'],d['document_no'],request.user,d['note'])
            messages.success(request,f'Mutasi manual #{proposal.pk} diajukan; saldo tidak berubah sampai manager menyetujui.')
            return redirect('inventory_manual_requests')
        except (ValidationError,IntegrityError) as exc:
            form.add_error(None, 'Nomor dokumen telah digunakan.' if isinstance(exc,IntegrityError) else exc)
    return render(request,'inventory/form.html',page_context(
        request,form=form,title='Usulkan barang masuk / keluar',
        subtitle='Perubahan saldo menunggu persetujuan manager lain. Tidak ada posting langsung.',
        submit_label='Ajukan mutasi',back_url='inventory_overview'))


@active_user
def request_part(request):
    if is_sparepart_manager(request.user) and not is_stock_admin(request.user):
        raise PermissionDenied('Manager bertugas untuk review dan monitoring.')
    form = RequestForm(request.POST or None, user=request.user,
                       initial={'part': request.GET.get('part', '')} if request.method == 'GET' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            req = make_request(form, request.user)
            messages.success(request, f'Permintaan #{req.pk} dikirim. '+('Saldo tersedia sudah dikurangi saat pengajuan.' if req.request_type=='consumption' else 'Menunggu manager; saldo belum bertambah.'))
            return redirect('inventory_requests')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'inventory/form.html', page_context(
        request, form=form, title='Minta sparepart',
        subtitle='Ajukan dari HP. Jika punya work order yang terbuka, boleh ditautkan.',
        submit_label='Kirim kebutuhan sparepart', back_url='inventory_requests'))


@active_user
@require_GET
def requests(request):
    qs = PartRequest.objects.select_related('part','order','requested_by','decided_by','fulfilled_by')
    if not can_monitor(request.user):
        permitted = Q(requested_by=request.user)
        if is_stock_admin(request.user):
            permitted |= Q(approval_route='stock_admin')
        if is_sparepart_manager(request.user):
            permitted |= Q(approval_route='manager')
        qs = qs.filter(permitted).distinct()
    status = request.GET.get('status','')
    if status in dict(PartRequest.STATUS):
        qs = qs.filter(status=status)
    page = Paginator(qs, 40).get_page(request.GET.get('page'))
    page.object_list = list(page.object_list)
    for item in page.object_list:
        item.may_decide = can_approve_request(request.user, item)
        item.may_cancel = item.request_type=='consumption' and item.status in ('pending','approved','partial') and (item.requested_by_id==request.user.pk or is_stock_admin(request.user))
    return render(request, 'inventory/requests.html', page_context(
        request, page=page, status=status))


@active_user
def request_decide(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    form = DecisionForm(request.POST)
    if form.is_valid():
        try:
            item = review_request(pk, request.user, form.cleaned_data['action'], form.cleaned_data['note'])
            messages.success(request, 'Permintaan #' + str(item.pk) + ' ' + item.get_status_display().lower() + '.')
        except (PartRequest.DoesNotExist, ValidationError) as exc:
            _show_error(request, exc)
    else:
        for errs in form.errors.values():
            messages.error(request, ', '.join(str(x) for x in errs))
    return redirect('inventory_requests')


@active_user
def request_issue(request, pk):
    if not can_manage(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        fulfill_request(pk, request.user, request.POST.get('quantity') or None)
        messages.success(request, 'Serah terima dicatat. Saldo tidak dikurangi dua kali.')
    except (PartRequest.DoesNotExist, ValidationError) as exc:
        _show_error(request, exc)
    return redirect('inventory_requests')


@active_user
def request_cancel(request, pk):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    try:
        cancel_request(pk,request.user,request.POST.get('reason',''))
        messages.success(request,'Permintaan dibatalkan. Sisa debit stok, jika ada, dikembalikan satu kali.')
    except (PartRequest.DoesNotExist, ValidationError) as exc:_show_error(request,exc)
    return redirect('inventory_requests')


@active_user
def request_return(request,pk):
    if not can_manage(request.user):raise PermissionDenied
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    try:
        return_issued(pk,request.user,request.POST.get('quantity'),request.POST.get('reason',''))
        messages.success(request,'Retur fisik ditambahkan ke stok dan dicatat dalam ledger.')
    except (PartRequest.DoesNotExist,ValidationError) as exc:_show_error(request,exc)
    return redirect('inventory_requests')


@active_user
@require_GET
def stocktakes(request):
    if not can_monitor(request.user):
        raise PermissionDenied
    return render(request, 'inventory/stocktakes.html', page_context(
        request, sessions=Stocktake.objects.select_related('created_by','posted_by')[:40]))


@active_user
def stocktake_new(request):
    if not can_manage(request.user):
        raise PermissionDenied
    form = StocktakeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            opname = start_stocktake(form.cleaned_data['title'], request.user)
            messages.success(request, f'Opname #{opname.pk} dibuat. Isi semua stok fisik sebelum posting.')
            return redirect('inventory_stocktake_detail', pk=opname.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'inventory/form.html', page_context(
        request, form=form, title='Mulai stock opname',
        subtitle='Saldo buku difoto saat mulai. Bila stok berubah saat menghitung, posting akan ditolak agar tidak menimpa transaksi lain.',
        submit_label='Buat sesi opname', back_url='inventory_stocktakes'))


@active_user
@require_GET
def stocktake_detail(request, pk):
    if not can_monitor(request.user):
        raise PermissionDenied
    opname = get_object_or_404(Stocktake.objects.select_related('created_by','posted_by'), pk=pk)
    lines = StocktakeLine.objects.filter(stocktake=opname).select_related('part','updated_by')
    progress = lines.filter(counted_qty__isnull=False).count()
    page = Paginator(lines, 35).get_page(request.GET.get('page'))
    return render(request, 'inventory/stocktake_detail.html', page_context(
        request, opname=opname, page=page, progress=progress, total_lines=lines.count(),
        may_post=is_sparepart_manager(request.user) and opname.created_by_id!=request.user.pk))


@active_user
def stocktake_count(request, pk, line_id):
    if not can_manage(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    form = CountForm(request.POST)
    if form.is_valid():
        try:
            count_line(pk, line_id, form.cleaned_data['counted_qty'], request.user)
            messages.success(request, 'Hasil hitung fisik tersimpan.')
        except (Stocktake.DoesNotExist, StocktakeLine.DoesNotExist, ValidationError) as exc:
            _show_error(request, exc)
    else:
        messages.error(request, 'Jumlah fisik harus bilangan bulat nol atau positif.')
    page = request.POST.get('page', '1')
    return redirect('inventory_stocktake_detail', pk=pk) if not page.isdigit() else redirect('/inventory/opname/'+str(pk)+'/?page='+page)


@active_user
def stocktake_post(request, pk):
    if not is_sparepart_manager(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if request.POST.get('confirm') != 'POSTING':
        messages.error(request, 'Konfirmasi posting tidak sesuai.')
        return redirect('inventory_stocktake_detail', pk=pk)
    try:
        changes = post_stocktake(pk, request.user)
        messages.success(request, f'Stock opname diposting. {changes} koreksi stok dicatat.')
    except (Stocktake.DoesNotExist, ValidationError) as exc:
        _show_error(request, exc)
    return redirect('inventory_stocktake_detail', pk=pk)


@active_user
def stocktake_cancel(request, pk):
    if not can_manage(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if request.POST.get('confirm') != 'BATAL':
        messages.error(request, 'Konfirmasi pembatalan tidak sesuai.')
        return redirect('inventory_stocktake_detail', pk=pk)
    try:
        cancel_stocktake(pk, request.user, request.POST.get('reason', ''))
        messages.success(request, 'Sesi opname dibatalkan. Hasil hitung tersimpan sebagai riwayat, tidak ada koreksi stok.')
    except (Stocktake.DoesNotExist, ValidationError) as exc:
        _show_error(request, exc)
    return redirect('inventory_stocktake_detail', pk=pk)


@active_user
def import_movements(request):
    if not can_manage(request.user):
        raise PermissionDenied
    if request.method == 'POST':
        upload = request.FILES.get('file')
        if upload is None:
            messages.error(request, 'Pilih file .xlsx atau .csv terlebih dahulu.')
        else:
            try:
                rows, fingerprint, filename = parse_uploaded(upload)
                batch = import_stock_rows(rows, fingerprint, filename, request.user,request.POST.get('document_id',''))
                messages.success(request, f'{batch.row_count} baris impor diterima sebagai pengajuan. Saldo tetap sampai manager memposting.')
                return redirect('inventory_import_batches')
            except (ValidationError, IntegrityError) as exc:
                _show_error(request, exc) if isinstance(exc, ValidationError) else messages.error(request, 'Impor ditolak: file identik telah diproses atau transaksi bersamaan. Tidak ada mutasi parsial.')
    elif request.method != 'GET':
        return HttpResponseNotAllowed(['GET','POST'])
    return render(request, 'inventory/import_movements.html', page_context(request))


@active_user
@require_GET
def movement_template_csv(request):
    if not can_manage(request.user):
        raise PermissionDenied
    import csv
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="template-mutasi-sparepart.csv"'
    response['Cache-Control'] = 'private, no-store'
    writer=csv.writer(response)
    response.write('\ufeff')
    writer.writerow(HEADERS)
    return response


@active_user
@require_GET
def movement_template_xlsx(request):
    if not can_manage(request.user):
        raise PermissionDenied
    from openpyxl import Workbook
    import io
    wb=Workbook()
    sheet=wb.active
    sheet.title='Mutasi'
    sheet.append(HEADERS)
    for col in sheet[1]:
        col.font=col.font.copy(bold=True)
    # Preserve codes such as 001 when users type them into Excel manually.
    for row in range(2, 502):
        sheet.cell(row=row, column=1).number_format = '@'
    sheet.column_dimensions['A'].width=24
    sheet.column_dimensions['B'].width=20
    sheet.column_dimensions['C'].width=16
    sheet.column_dimensions['D'].width=40
    buffer=io.BytesIO();wb.save(buffer)
    response=HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']='attachment; filename="template-mutasi-sparepart.xlsx"'
    response['Cache-Control']='private, no-store'
    return response


@active_user
@require_GET
def import_batches(request):
    if not can_monitor(request.user):raise PermissionDenied
    qs=StockImportBatch.objects.select_related('actor','decided_by')
    if not is_sparepart_manager(request.user):qs=qs.filter(actor=request.user)
    batches=Paginator(qs,35).get_page(request.GET.get('page'))
    return render(request,'inventory/approval_batches.html',page_context(request,items=batches,type='import',title='Impor mutasi menunggu approval'))

@active_user
def import_decide(request,pk):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    try:
        result=review_import(pk,request.user,request.POST.get('action'),request.POST.get('note',''))
        messages.success(request,f'Impor #{result.pk}: {result.get_status_display()}.')
    except (StockImportBatch.DoesNotExist,ValidationError) as exc:_show_error(request,exc)
    return redirect('inventory_import_batches')

@active_user
@require_GET
def manual_requests(request):
    if not can_monitor(request.user):raise PermissionDenied
    qs=ManualStockRequest.objects.select_related('part','requested_by','decided_by')
    if not is_sparepart_manager(request.user):qs=qs.filter(requested_by=request.user)
    items=Paginator(qs,35).get_page(request.GET.get('page'))
    return render(request,'inventory/approval_batches.html',page_context(request,items=items,type='manual',title='Mutasi manual menunggu approval'))

@active_user
def manual_decide(request,pk):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    try:
        result=review_manual(pk,request.user,request.POST.get('action'),request.POST.get('note',''))
        messages.success(request,f'Mutasi manual #{result.pk}: {result.get_status_display()}.')
    except (ManualStockRequest.DoesNotExist,ValidationError) as exc:_show_error(request,exc)
    return redirect('inventory_manual_requests')

@active_user
@require_GET
def audit_inventory(request):
    if not can_monitor(request.user):raise PermissionDenied
    events=InventoryAudit.objects.select_related('actor')
    if not is_sparepart_manager(request.user):events=events.filter(actor=request.user)
    return render(request,'inventory/audit.html',page_context(request,page=Paginator(events,50).get_page(request.GET.get('page'))))

@active_user
@require_GET
def procurement_export(request):
    if not is_sparepart_manager(request.user):raise PermissionDenied
    import csv
    from maintenance.importing import safe_cell
    resp=HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition']='attachment; filename="laporan-pengadaan-sparepart.csv"'
    resp['Cache-Control']='private, no-store'
    resp.write('\ufeff')
    writer=csv.writer(resp)
    writer.writerow(['ID','Dibuat','Kode','Sparepart','Satuan','Jumlah diminta','Jumlah disetujui','Jumlah saldo ditambah',
                     'Status','Peminta','Approver','Tanggal approval','Alasan','Catatan manager',
                     'Nomor pengajuan','Supplier','Tanggal dibutuhkan','Estimasi harga satuan Rp','Estimasi total Rp'])
    qs=PartRequest.objects.filter(request_type='replenishment').select_related('part','requested_by','decided_by').order_by('-created_at','-pk')
    date_from=request.GET.get('from','')[:10];date_to=request.GET.get('to','')[:10]
    import datetime
    for val in (date_from,date_to):
        if val:
            try:datetime.date.fromisoformat(val)
            except ValueError:raise ValidationError('Tanggal harus YYYY-MM-DD.')
    if date_from:qs=qs.filter(created_at__date__gte=date_from)
    if date_to:qs=qs.filter(created_at__date__lte=date_to)
    for row in qs[:20000].iterator(chunk_size=300):
        qty=str(row.quantity)
        credited=row.ledger_phase=='credited'
        unit_price=row.estimated_unit_price
        estimated_total=unit_price*row.quantity if unit_price is not None else ''
        writer.writerow([safe_cell(v) for v in (row.pk,row.created_at,row.part.sku,row.part.name,row.part.unit,qty,
            qty if row.decided_by and row.status!='rejected' else 0,qty if credited else 0,row.get_status_display(),
            row.requested_by,row.decided_by or '',row.decided_at or '',row.note,row.manager_note,
            row.procurement_ref,row.supplier,row.needed_by or '',unit_price if unit_price is not None else '',estimated_total)])
    resp['X-Export-Limit']='20000';return resp
