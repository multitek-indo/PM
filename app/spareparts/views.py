import os
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET
from maintenance.models import WorkOrder, AuditEvent
from maintenance.services import visible_orders
from .forms import SparepartPhotoForm
from .image_storage import normalize_image, open_private, remove_private, save_private
from .models import SparepartPhoto


@login_required
def upload_photo(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not request.user.is_active:
        raise PermissionDenied
    order = get_object_or_404(visible_orders(request.user), pk=pk)
    if order.status != 'open' or order.assigned_to_id != request.user.pk:
        raise PermissionDenied('Foto hanya dapat ditambahkan oleh teknisi aktif yang ditugaskan, ketika pekerjaan terbuka.')
    form = SparepartPhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        for errors in form.errors.values():
            for message in errors:
                messages.error(request, message)
        return redirect('order_detail', pk=pk)
    try:
        data = normalize_image(form.cleaned_data['photo'])
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
        return redirect('order_detail', pk=pk)
    filename = None
    try:
        with transaction.atomic():
            # Lock parent to prevent concurrent uploads bypassing the per-order limit.
            locked = WorkOrder.objects.select_for_update().get(pk=pk)
            if locked.status != 'open' or locked.assigned_to_id != request.user.pk:
                raise PermissionDenied('Penugasan/status pekerjaan berubah. Foto tidak ditambahkan.')
            if locked.sparepart_photos.count() >= 10:
                messages.error(request, 'Maksimal 10 foto per work order.')
                return redirect('order_detail', pk=pk)
            filename = save_private(data)
            photo = SparepartPhoto.objects.create(
                order=locked, kind=form.cleaned_data['kind'],
                part_name=form.cleaned_data['part_name'].strip(),
                note=form.cleaned_data['note'].strip(),
                filename=filename, uploaded_by=request.user,
            )
            AuditEvent.objects.create(
                order=locked, actor=request.user, action='sparepart_photo_added',
                detail={'photo_id': photo.pk, 'part_name': photo.part_name, 'kind': photo.kind},
            )
    except BaseException:
        if filename:
            remove_private(filename)
        raise
    messages.success(request, 'Foto sparepart disimpan dan dapat dilihat supervisor pada work order ini.')
    return redirect('order_detail', pk=pk)


@login_required
@require_GET
def view_photo(request, photo_id):
    if not request.user.is_active:
        raise PermissionDenied
    photo = get_object_or_404(
        SparepartPhoto.objects.select_related('order'),
        pk=photo_id, order_id__in=visible_orders(request.user).values_list('pk', flat=True),
    )
    try:
        image_file = open_private(photo.filename)
    except OSError as exc:
        raise Http404('Foto tidak ditemukan di penyimpanan.') from exc
    response = FileResponse(image_file, content_type='image/jpeg')
    response['Cache-Control'] = 'private, no-store, max-age=0'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Content-Disposition'] = f'inline; filename="sparepart-{photo.pk}.jpg"'
    return response
