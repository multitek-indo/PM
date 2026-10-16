"""Authoritative stock transactions; POST handlers must not write balances directly."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from maintenance.services import supervisor, visible_orders
from .models import (Part, PartRequest, StockMovement, Stocktake, StocktakeLine, StockImportBatch,
                     StockImportLine, ManualStockRequest, InventoryAudit, LIMIT)


def can_manage(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_superuser or user.groups.filter(name='Pengelola Stok Sparepart').exists()))


def ensure_manager(user):
    if not can_manage(user):
        raise PermissionDenied('Hanya pengelola stok yang dapat mengajukan perubahan persediaan.')


def is_stock_admin(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_superuser or user.groups.filter(name='Pengelola Stok Sparepart').exists()))


def is_sparepart_manager(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_superuser or user.has_perm('inventory.approve_admin_request')))



def can_monitor(user):
    return bool(user.is_authenticated and user.is_active and (
        can_manage(user) or is_sparepart_manager(user) or user.has_perm('inventory.view_all_inventory')))

def _audit(entity_type, pk, action, actor, before=None, after=None, reason=''):
    return InventoryAudit.objects.create(entity_type=entity_type, entity_pk=str(pk),
        action=action, actor=actor, before=before or {}, after=after or {}, reason=reason[:600])

def _snapshot_part(part):
    return {key:str(getattr(part,key)) for key in ('sku','name','unit','location','machine_type','min_qty','active','current_qty')}

def route_for_requester(user):
    # Approval direction is defined by the business role, never by Supervisor PM.
    return 'manager' if is_stock_admin(user) else 'stock_admin'


def can_approve_request(user, req):
    if not user.is_authenticated or not user.is_active or user.pk == req.requested_by_id:
        return False
    return is_sparepart_manager(user) if req.approval_route == 'manager' else is_stock_admin(user)


def whole(value, zero=False):
    try:
        n = Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        raise ValidationError('Jumlah harus bilangan bulat.')
    if not n.is_finite() or n != n.to_integral_value():
        raise ValidationError('Jumlah harus bilangan bulat tanpa pecahan.')
    if n < 0 or (n == 0 and not zero) or n > Decimal('999999999'):
        raise ValidationError('Jumlah harus dalam batas 1-999999999 (nol hanya untuk saldo/minimum).')
    return n


def _move(part, actor, kind, delta, note='', request=None, stocktake=None, import_batch=None, event_key=None):
    """Call inside transaction.atomic after obtaining select_for_update on Part."""
    before = whole(part.current_qty, zero=True)
    signed = whole(abs(delta))
    delta = signed if delta > 0 else -signed
    after = before + delta
    if after < 0:
        raise ValidationError('Stok tidak cukup. Pengeluaran dibatalkan.')
    if after > LIMIT:
        raise ValidationError('Jumlah melebihi batas stok maksimum.')
    if delta == 0:
        return None
    part.current_qty = after
    part.save(update_fields=['current_qty', 'updated_at'])
    return StockMovement.objects.create(part=part, kind=kind, qty_delta=delta,
                                        before_qty=before, after_qty=after, note=note,
                                        request=request, stocktake=stocktake, import_batch=import_batch, actor=actor,
                                        event_key=event_key)


@transaction.atomic
def move_stock(part_id, kind, amount, actor, note):
    """Legacy emergency API; only a superuser may bypass explicit approval.

    The public management form never calls this function. A unique event is
    recorded with a clear emergency indicator to make exceptions auditable.
    """
    if not (actor.is_authenticated and actor.is_active and actor.is_superuser):
        raise PermissionDenied('Mutasi langsung dibatasi untuk akun admin software.')
    if kind not in ('receive','issue') or not str(note or '').strip():
        raise ValidationError('Jenis dan referensi wajib diisi.')
    amount = whole(amount)
    part = Part.objects.select_for_update().get(pk=part_id, active=True)
    moved = _move(part, actor, kind, amount if kind=='receive' else -amount,
                  '[EMERGENCY SUPERUSER] '+str(note).strip()[:570])
    _audit('part',part.pk,'emergency_movement',actor,after={'movement':moved.pk,'delta':str(moved.qty_delta)},reason=str(note))
    return moved


@transaction.atomic
def make_request(form, actor):
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied
    # Software-admin and store roles are distinct from a technician account.
    from maintenance.models import WorkOrder
    if not is_stock_admin(actor) and not actor.is_superuser and not (
            actor.groups.filter(name='Teknisi PM').exists() or WorkOrder.objects.filter(assigned_to=actor,status='open').exists()):
        raise PermissionDenied('Hanya teknisi bertugas atau admin sparepart dapat membuat permintaan.')
    if is_sparepart_manager(actor) and not is_stock_admin(actor):
        raise PermissionDenied('Manager memantau dan menyetujui; tidak melakukan permintaan teknisi.')
    order = form.cleaned_data['order']
    if order and not visible_orders(actor).filter(pk=order.pk, status='open').exists():
        raise PermissionDenied('Anda tidak berhak memilih work order ini.')
    route = route_for_requester(actor)
    request_type = 'replenishment' if route=='manager' else 'consumption'
    if request_type=='replenishment' and order:
        raise ValidationError('Pengadaan stok tidak boleh ditautkan sebagai pemakaian work order.')
    item = form.save(commit=False)
    item.requested_by=actor
    item.approval_route=route
    item.request_type=request_type
    item.status='pending'
    item.quantity=whole(item.quantity)
    if request_type=='replenishment':
        item.procurement_ref=(item.procurement_ref or '').strip().upper()
        item.supplier=(item.supplier or '').strip()
    else:
        item.procurement_ref='';item.supplier='';item.estimated_unit_price=None;item.needed_by=None
    if request_type=='consumption':
        part=Part.objects.select_for_update().get(pk=item.part_id, active=True)
        # Reservation is represented as a stock book debit in the requested SOP.
        item.ledger_phase='debited'
        item.save()
        _move(part,actor,'request',-item.quantity,
              f'Permintaan teknisi #{item.pk} (dikurangi saat pengajuan)',
              request=item,event_key=f'request:{item.pk}:submit')
    else:
        item.ledger_phase='legacy'
        item.save()
    _audit('request',item.pk,'submitted',actor,after={'type':request_type,'quantity':str(item.quantity),'route':route})
    return item


@transaction.atomic
def review_request(request_id, actor, action, note):
    obj=PartRequest.objects.select_for_update().get(pk=request_id)
    if not can_approve_request(actor,obj):
        raise PermissionDenied('Anda tidak berhak memutuskan permintaan ini.')
    if obj.status!='pending' or action not in ('approve','reject'):
        raise ValidationError('Permintaan tidak lagi menunggu keputusan.')
    if action=='reject' and not (note or '').strip():
        raise ValidationError('Alasan penolakan wajib diisi.')
    if action=='approve' and obj.request_type=='replenishment':
        if obj.approval_route!='manager':
            raise ValidationError('Pengadaan hanya boleh disetujui manager.')
        part=Part.objects.select_for_update().get(pk=obj.part_id,active=True)
        _move(part,actor,'receive',whole(obj.quantity),
              f'Pengadaan disetujui manager #{obj.pk} (saldo administratif)',
              request=obj,event_key=f'request:{obj.pk}:approve')
        obj.ledger_phase='credited'
        obj.status='fulfilled'  # No additional issue/receipt action is possible.
        obj.fulfilled_by=actor
        obj.fulfilled_at=timezone.now()
    elif action=='reject':
        if obj.request_type=='consumption' and obj.ledger_phase=='debited':
            part=Part.objects.select_for_update().get(pk=obj.part_id)
            _move(part,actor,'request',whole(obj.quantity)-whole(obj.issued_qty,zero=True),
                  f'Pengembalian permintaan ditolak #{obj.pk}',request=obj,
                  event_key=f'request:{obj.pk}:reject')
            obj.ledger_phase='reversed'
        obj.status='rejected'
    else:
        obj.status='approved'
    obj.decided_by=actor;obj.decided_at=timezone.now();obj.manager_note=(note or '').strip()
    obj.save(update_fields=['status','ledger_phase','decided_by','decided_at','manager_note','fulfilled_by','fulfilled_at'])
    _audit('request',obj.pk,action,actor,after={'type':obj.request_type,'status':obj.status,'phase':obj.ledger_phase},reason=note or '')
    return obj


@transaction.atomic
def fulfill_request(request_id, actor, amount=None):
    ensure_manager(actor)
    obj=PartRequest.objects.select_for_update().get(pk=request_id)
    if obj.request_type!='consumption':
        raise ValidationError('Permintaan pengadaan tidak boleh dikeluarkan sebagai barang keluar.')
    if obj.status not in ('approved','partial'):
        raise ValidationError('Hanya pemakaian teknisi yang telah disetujui dapat diserahkan.')
    remaining=whole(obj.quantity)-whole(obj.issued_qty,zero=True)
    qty=whole(amount if amount is not None else remaining)
    if qty>remaining:
        raise ValidationError('Jumlah serah terima melebihi sisa permintaan.')
    if obj.order_id:
        # An old request must not be handed to a different WO assignee or after WO closure.
        from maintenance.models import WorkOrder
        current_order=WorkOrder.objects.get(pk=obj.order_id)
        if current_order.assigned_to_id!=obj.requested_by_id or current_order.status not in ('open','review'):
            raise ValidationError('Work order berubah/selesai; serah terima ditahan untuk peninjauan.')
    if obj.ledger_phase=='legacy':
        # Existing historical approvals had not debited on request creation.
        part=Part.objects.select_for_update().get(pk=obj.part_id,active=True)
        _move(part,actor,'request',-qty,f'Pemenuhan permintaan historis #{obj.pk}',
              request=obj,event_key=f'request:{obj.pk}:legacy_issue:{str(obj.issued_qty)}')
    elif obj.ledger_phase!='debited':
        raise ValidationError('Permintaan tidak memiliki saldo yang siap diserahkan.')
    obj.issued_qty=whole(obj.issued_qty,zero=True)+qty
    obj.status='fulfilled' if obj.issued_qty==obj.quantity else 'partial'
    obj.fulfilled_by=actor;obj.fulfilled_at=timezone.now()
    obj.save(update_fields=['issued_qty','status','fulfilled_by','fulfilled_at'])
    _audit('request',obj.pk,'handed_over',actor,after={'issued':str(qty),'total_issued':str(obj.issued_qty)},reason='Serah terima tanpa debit ulang')
    return obj


@transaction.atomic
def cancel_request(request_id,actor,reason):
    reason=(reason or '').strip()
    if len(reason)<3 or len(reason)>600:
        raise ValidationError('Alasan pembatalan wajib (3-600 karakter).')
    obj=PartRequest.objects.select_for_update().get(pk=request_id)
    if obj.request_type!='consumption' or obj.status not in ('pending','approved','partial'):
        raise ValidationError('Hanya pemakaian yang belum sepenuhnya diserahkan dapat dibatalkan.')
    if obj.requested_by_id!=actor.pk and not is_stock_admin(actor):
        raise PermissionDenied
    remaining=whole(obj.quantity)-whole(obj.issued_qty,zero=True)
    if obj.ledger_phase=='debited' and remaining>0:
        part=Part.objects.select_for_update().get(pk=obj.part_id)
        _move(part,actor,'request',remaining,f'Pengembalian sisa permintaan #{obj.pk}',
              request=obj,event_key=f'request:{obj.pk}:cancel')
        obj.ledger_phase='reversed'
    obj.status='cancelled';obj.cancelled_at=timezone.now();obj.cancelled_by=actor;obj.cancel_note=reason
    obj.save(update_fields=['status','ledger_phase','cancelled_at','cancelled_by','cancel_note'])
    _audit('request',obj.pk,'cancelled',actor,after={'returned':str(remaining),'issued':str(obj.issued_qty)},reason=reason)
    return obj


@transaction.atomic
def return_issued(request_id,actor,quantity,reason):
    ensure_manager(actor)
    reason=(reason or '').strip()
    if len(reason)<3:raise ValidationError('Bukti retur wajib diisi.')
    obj=PartRequest.objects.select_for_update().get(pk=request_id)
    if obj.request_type!='consumption' or obj.status not in ('partial','fulfilled','cancelled'):
        raise ValidationError('Belum ada serah terima yang dapat diretur.')
    qty=whole(quantity)
    remaining=whole(obj.issued_qty,zero=True)-whole(obj.returned_qty,zero=True)
    if qty>remaining:raise ValidationError('Jumlah retur melebihi jumlah barang yang telah diserahkan.')
    part=Part.objects.select_for_update().get(pk=obj.part_id)
    _move(part,actor,'request',qty,f'Retur fisik permintaan #{obj.pk}: '+reason[:480],
          request=obj,event_key=f'request:{obj.pk}:return:{str(obj.returned_qty)}')
    obj.returned_qty=whole(obj.returned_qty,zero=True)+qty
    obj.save(update_fields=['returned_qty'])
    _audit('request',obj.pk,'returned',actor,after={'qty':str(qty),'returned_total':str(obj.returned_qty)},reason=reason)
    return obj


@transaction.atomic
def start_stocktake(title, actor):
    ensure_manager(actor)
    # Serialise creation against part updates/other stocktakes on PostgreSQL.
    from django.db import connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(14328, 401)')
    if Stocktake.objects.filter(status='draft').exists():
        raise ValidationError('Masih ada opname yang belum diposting. Selesaikan dahulu.')
    parts = list(Part.objects.select_for_update().filter(active=True).order_by('pk'))
    if not parts:
        raise ValidationError('Master sparepart aktif masih kosong.')
    if len(parts) > 3000:
        raise ValidationError('Lebih dari 3.000 sparepart aktif: gunakan pengembangan opname bertahap.')
    latest = {d['part_id']:d['latest'] for d in StockMovement.objects.filter(part__in=parts)
              .values('part_id').annotate(latest=Max('pk'))}
    opname = Stocktake.objects.create(title=title, created_by=actor)
    StocktakeLine.objects.bulk_create([StocktakeLine(stocktake=opname, part=p, book_qty=p.current_qty,
                                    book_movement_id=latest.get(p.pk) or 0)
                                       for p in parts], batch_size=200)
    return opname


@transaction.atomic
def count_line(stocktake_id, line_id, quantity, actor):
    ensure_manager(actor)
    opname = Stocktake.objects.select_for_update().get(pk=stocktake_id)
    if opname.status != 'draft':
        raise ValidationError('Opname telah diposting.')
    quantity = whole(quantity, zero=True)
    line = StocktakeLine.objects.select_for_update().get(pk=line_id, stocktake=opname)
    line.counted_qty = quantity
    line.updated_by = actor
    line.updated_at = timezone.now()
    line.save(update_fields=['counted_qty','updated_by','updated_at'])
    return line


@transaction.atomic
def post_stocktake(stocktake_id, actor):
    if not is_sparepart_manager(actor):
        raise PermissionDenied('Hanya manager sparepart yang boleh memposting koreksi.')
    opname = Stocktake.objects.select_for_update().get(pk=stocktake_id)
    if opname.created_by_id == actor.pk:
        raise PermissionDenied('Pembuat opname tidak boleh menyetujui opname sendiri.')
    if opname.status != 'draft':
        raise ValidationError('Opname ini sudah pernah diposting.')
    lines = list(StocktakeLine.objects.filter(stocktake=opname).select_related('part').order_by('part_id'))
    if not lines or any(line.counted_qty is None for line in lines):
        raise ValidationError('Semua sparepart harus dihitung sebelum posting opname.')
    parts = {p.pk:p for p in Part.objects.select_for_update().filter(pk__in=[l.part_id for l in lines]).order_by('pk')}
    if set(parts) != set(Part.objects.filter(active=True).values_list('pk', flat=True)):
        raise ValidationError('Daftar sparepart aktif berubah sejak opname dimulai. Buat sesi opname baru.')
    latest = {d['part_id']:d['latest'] for d in StockMovement.objects.filter(part_id__in=parts)
              .values('part_id').annotate(latest=Max('pk'))}
    for line in lines:
        if (parts[line.part_id].current_qty != line.book_qty or
                (latest.get(line.part_id) or 0) != line.book_movement_id):
            raise ValidationError('Stok berubah setelah opname dimulai. Catatan fisik disimpan, tetapi perlu opname baru sebelum koreksi.')
    changes = 0
    for line in lines:
        delta = whole(line.counted_qty, zero=True) - whole(line.book_qty, zero=True)
        if delta:
            _move(parts[line.part_id], actor, 'opname', delta,
                  f'Opname #{opname.pk}: {opname.title}', stocktake=opname)
            changes += 1
    opname.status = 'posted'
    opname.posted_at = timezone.now()
    opname.posted_by = actor
    opname.save(update_fields=['status', 'posted_at', 'posted_by'])
    _audit('stocktake',opname.pk,'posted',actor,after={'adjustments':changes,'creator':opname.created_by_id})
    return changes


@transaction.atomic
def cancel_stocktake(stocktake_id, actor, reason):
    ensure_manager(actor)
    opname = Stocktake.objects.select_for_update().get(pk=stocktake_id)
    reason = (reason or '').strip()
    if opname.status != 'draft':
        raise ValidationError('Hanya opname draf yang dapat dibatalkan.')
    if len(reason) < 3 or len(reason) > 600:
        raise ValidationError('Masukkan alasan pembatalan (3-600 karakter).')
    opname.status = 'cancelled'
    opname.cancelled_by = actor
    opname.cancelled_at = timezone.now()
    opname.cancel_note = reason
    opname.save(update_fields=['status','cancelled_by','cancelled_at','cancel_note'])
    return opname


@transaction.atomic
def import_stock_rows(rows, fingerprint, filename, actor, document_id=None):
    """Stage immutable rows. Manager later approves and posts atomically."""
    ensure_manager(actor)
    import hashlib,json
    if not rows or len(rows)>5000:
        raise ValidationError('Impor harus berisi 1-5000 baris.')
    kinds={row['kind'] for row in rows}
    if len(kinds)!=1 or not kinds.issubset({'receive','issue'}):
        raise ValidationError('Pisahkan barang masuk dan keluar ke dokumen impor berbeda.')
    canonical=[{'sku':r['sku'],'kind':r['kind'],'qty':str(whole(r['quantity'])),'note':str(r['note']).strip()} for r in rows]
    semhash=hashlib.sha256(json.dumps(sorted(canonical,key=lambda item:(item['sku'],item['kind'],item['qty'],item['note'])),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    doc_id=(document_id or 'AUTO-'+semhash[:40]).strip().upper()
    if not doc_id or len(doc_id)>90:
        raise ValidationError('Nomor dokumen impor tidak valid.')
    if StockImportBatch.objects.filter(document_id=doc_id).exists() or StockImportBatch.objects.filter(semantic_hash=semhash).exists() or StockImportBatch.objects.filter(fingerprint=fingerprint).exists():
        raise ValidationError('Dokumen atau transaksi serupa sudah pernah diajukan. Periksa riwayat sebelum mengimpor ulang.')
    codes={r['sku'] for r in rows}
    parts=list(Part.objects.filter(sku__in=codes,active=True).order_by('pk'))
    by_sku={p.sku:p for p in parts}
    missing=codes-set(by_sku)
    if missing:raise ValidationError('Sparepart tidak ditemukan: '+', '.join(sorted(missing)[:8]))
    batch=StockImportBatch.objects.create(fingerprint=fingerprint,filename=filename[:200],document_id=doc_id,semantic_hash=semhash,kind=next(iter(kinds)),row_count=len(rows),actor=actor,status='pending')
    StockImportLine.objects.bulk_create([StockImportLine(batch=batch,part=by_sku[r['sku']],line_no=i,kind=r['kind'],quantity=whole(r['quantity']),reference=str(r['note']).strip()) for i,r in enumerate(rows,1)],batch_size=200)
    _audit('import',batch.pk,'submitted',actor,after={'document':doc_id,'rows':len(rows),'type':batch.kind})
    return batch


@transaction.atomic
def review_import(batch_id,actor,action,note=''):
    if not is_sparepart_manager(actor):raise PermissionDenied
    batch=StockImportBatch.objects.select_for_update().get(pk=batch_id)
    if batch.actor_id==actor.pk:raise PermissionDenied('Impor tidak boleh disetujui pengunggah.')
    if batch.status!='pending' or action not in ('approve','reject'):
        raise ValidationError('Status impor bukan menunggu keputusan.')
    if action=='reject':
        if not (note or '').strip():raise ValidationError('Alasan penolakan wajib.')
        batch.status='rejected'
    else:
        lines=list(StockImportLine.objects.filter(batch=batch).order_by('line_no'))
        parts={p.pk:p for p in Part.objects.select_for_update().filter(pk__in={l.part_id for l in lines}).order_by('pk')}
        if len(parts)!=len({l.part_id for l in lines}):
            raise ValidationError('Master impor berubah.')
        for line in lines:
            part=parts[line.part_id]
            if not part.active:raise ValidationError('Sparepart tidak aktif: '+part.sku)
            _move(part,actor,line.kind,whole(line.quantity) if line.kind=='receive' else -whole(line.quantity),
                  f'Impor disetujui #{batch.pk}, baris {line.line_no}: '+line.reference[:500],
                  import_batch=batch,event_key=f'import:{batch.pk}:row:{line.line_no}')
        batch.status='posted'
    batch.decided_by=actor;batch.decided_at=timezone.now();batch.decision_note=(note or '').strip()
    batch.save(update_fields=['status','decided_by','decided_at','decision_note'])
    _audit('import',batch.pk,action,actor,after={'status':batch.status,'rows':batch.row_count},reason=note)
    return batch


@transaction.atomic
def propose_manual(part_id,kind,quantity,document_no,actor,note):
    ensure_manager(actor)
    doc=(document_no or '').strip().upper()
    if len(doc)<3 or len(doc)>90 or not (note or '').strip():
        raise ValidationError('Nomor dokumen (3-90) dan alasan wajib.')
    if kind not in ('receive','issue'):raise ValidationError('Jenis mutasi tidak valid.')
    part=Part.objects.get(pk=part_id,active=True)
    obj=ManualStockRequest.objects.create(part=part,kind=kind,quantity=whole(quantity),document_no=doc,
                                           note=note.strip(),requested_by=actor)
    _audit('manual',obj.pk,'submitted',actor,after={'kind':kind,'quantity':str(obj.quantity),'document':doc})
    return obj


@transaction.atomic
def review_manual(manual_id,actor,action,note=''):
    if not is_sparepart_manager(actor):raise PermissionDenied
    obj=ManualStockRequest.objects.select_for_update().get(pk=manual_id)
    if obj.requested_by_id==actor.pk:raise PermissionDenied('Tidak boleh menyetujui permintaan sendiri.')
    if obj.status!='pending' or action not in ('approve','reject'):
        raise ValidationError('Permintaan manual tidak menunggu keputusan.')
    if action=='approve':
        part=Part.objects.select_for_update().get(pk=obj.part_id,active=True)
        _move(part,actor,obj.kind,whole(obj.quantity) if obj.kind=='receive' else -whole(obj.quantity),
              f'Mutasi manual disetujui #{obj.pk}: '+obj.document_no+' '+obj.note[:300],event_key=f'manual:{obj.pk}:approve')
        obj.status='posted'
    else:
        if not (note or '').strip():raise ValidationError('Alasan penolakan wajib.')
        obj.status='rejected'
    obj.decided_by=actor;obj.decided_at=timezone.now();obj.decision_note=(note or '').strip()
    obj.save(update_fields=['status','decided_by','decided_at','decision_note'])
    _audit('manual',obj.pk,action,actor,after={'status':obj.status},reason=note)
    return obj
