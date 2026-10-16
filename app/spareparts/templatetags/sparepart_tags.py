from django import template
from maintenance.services import visible_orders
from spareparts.forms import SparepartPhotoForm
from spareparts.models import SparepartPhoto

register = template.Library()


@register.inclusion_tag('spareparts/panel.html', takes_context=True)
def sparepart_panel(context, order, user):
    visible = user.is_authenticated and user.is_active and visible_orders(user).filter(pk=order.pk).exists()
    if not visible:
        return {'photos': [], 'can_upload_photo': False}
    photos = list(SparepartPhoto.objects.filter(order=order).select_related('uploaded_by'))
    return {
        'order': order,
        'photos': photos,
        'form_photo': SparepartPhotoForm(),
        'can_upload_photo': order.status == 'open' and order.assigned_to_id == user.pk and len(photos) < 10,
        'photo_capacity': max(0, 10 - len(photos)),
    }
