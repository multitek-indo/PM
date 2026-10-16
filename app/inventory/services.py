"""Authoritative stock transactions; POST handlers must not write balances directly."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from maintenance.services import supervisor, visible_orders
from .models import Part, PartRequest, StockMovement, Stocktake, StocktakeLine, StockImportBatch, LIMIT


def can_manage(user):
    return bool(user.is_authenticated and user.is_active and
                (supervisor(user) or user.groups.filter(name='Pengelola Stok Sparepart').exists()))


def ensure_manager(user):
    if not can_manage(user):
        raise PermissionDenied('Hanya supervisor atau pengelola stok yang dapat mengubah persediaan.')


def is_stock_admin(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_superuser or user.groups.filter(name='Pengelola Stok Sparepart').exists()))


def is_sparepart_manager(user):
    return bool(user.is_authenticated and user.is_active and
                (user.is_superuser or user.has_perm('inventory.approve_admin_request')))


def route_for_requester(user):
    # Snapshot requester tier: group changes later never reroute pending requests.
    return 'manager' if can_manage(user) or is_sparepart_manager(user) else 'stock_admin'


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


def _move(part, actor, kind, delta, note='', request=None, stocktake=None, import_batch=None):
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
                                        request=request, stocktake=stocktake, import_batch=import_batch, actor=actor)


@transaction.atomic
def move_stock(part_id, kind, amount, actor, note):
    ensure_manager(actor)
    if kind not in ('receive', 'issue'):
        raise ValidationError('Jenis mutasi tidak valid.')
    amount = whole(amount)
    part = Part.objects.select_for_update().get(pk=part_id, active=True)
    return _move(part, actor, kind, amount if kind == 'receive' else -amount, note)


@transaction.atomic
def make_request(form, actor):
    if not actor.is_active:
        raise PermissionDenied
    order = form.cleaned_data['order']
    if order and not visible_orders(actor).filter(pk=order.pk, status='open').exists():
        raise PermissionDenied('Anda tidak berhak memilih work order ini.')
    item = form.save(commit=False)
    item.requested_by = actor
    item.approval_route = route_for_requester(actor)
    item.status = 'pending'
    item.save()
    return item


@transaction.atomic
def review_request(request_id, actor, action, note):
    obj = PartRequest.objects.select_for_update().get(pk=request_id)
    if not can_approve_request(actor, obj):
        raise PermissionDenied('Anda tidak berhak memutuskan permintaan ini.')
    if obj.status != 'pending' or action not in ('approve', 'reject'):
        raise ValidationError('Permintaan tidak lagi menunggu keputusan.')
    if action == 'reject' and not note.strip():
        raise ValidationError('Alasan penolakan wajib diisi.')
    obj.status = 'approved' if action == 'approve' else 'rejected'
    obj.decided_by = actor
    obj.decided_at = timezone.now()
    obj.manager_note = note.strip()
    obj.save(update_fields=['status', 'decided_by', 'decided_at', 'manager_note'])
    return obj


@transaction.atomic
def fulfill_request(request_id, actor):
    ensure_manager(actor)
    obj = PartRequest.objects.select_for_update().get(pk=request_id)
    if obj.status != 'approved':
        raise ValidationError('Hanya permintaan yang disetujui dan belum dikeluarkan dapat dipenuhi.')
    part = Part.objects.select_for_update().get(pk=obj.part_id)
    if not part.active:
        raise ValidationError('Sparepart sudah nonaktif.')
    _move(part, actor, 'request', -whole(obj.quantity), f'Permintaan #{obj.pk}', request=obj)
    obj.status = 'fulfilled'
    obj.fulfilled_by = actor
    obj.fulfilled_at = timezone.now()
    obj.save(update_fields=['status','fulfilled_by','fulfilled_at'])
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
    ensure_manager(actor)
    opname = Stocktake.objects.select_for_update().get(pk=stocktake_id)
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
def import_stock_rows(rows, fingerprint, filename, actor):
    """Each file is applied exactly once, all rows or none, in stable lock order."""
    ensure_manager(actor)
    if StockImportBatch.objects.filter(fingerprint=fingerprint).exists():
        raise ValidationError('File identik sudah pernah diimpor. Tidak ada stok yang diubah.')
    codes = {row['sku'] for row in rows}
    parts = list(Part.objects.select_for_update().filter(sku__in=codes, active=True).order_by('pk'))
    by_sku = {p.sku: p for p in parts}
    unknown = sorted(codes - set(by_sku))
    if unknown:
        raise ValidationError('Kode sparepart tidak ditemukan/aktif: ' + ', '.join(unknown[:8]))
    balances = {sku: whole(p.current_qty, zero=True) for sku, p in by_sku.items()}
    for i, row in enumerate(rows, start=2):
        qty = whole(row['quantity'])
        if row['kind'] not in ('receive','issue'):
            raise ValidationError('Jenis mutasi tidak valid pada baris %d.' % i)
        balances[row['sku']] += qty if row['kind']=='receive' else -qty
        if not 0 <= balances[row['sku']] <= Decimal('999999999'):
            raise ValidationError('Baris %d: stok keluar melebihi saldo atau melebihi batas.' % i)
    batch = StockImportBatch.objects.create(fingerprint=fingerprint, filename=filename[:200],
                                            row_count=len(rows), actor=actor)
    for row in rows:
        qty = whole(row['quantity'])
        _move(by_sku[row['sku']], actor, row['kind'], qty if row['kind']=='receive' else -qty,
              row['note'], import_batch=batch)
    return batch
