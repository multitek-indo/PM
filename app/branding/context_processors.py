from django.conf import settings
from .models import CompanyProfile, DEFAULT_COMPANY_NAME


def company_identity(request):
    # One read per rendered request; never create/update data during GET.
    # Do not hide database errors with a blanket exception handler.
    name = CompanyProfile.objects.filter(pk=1).values_list('company_name', flat=True).first() or DEFAULT_COMPANY_NAME
    return {'pm_company_name': name, 'pm_company_initial': name[:1].upper(),
            'pm_app_version': settings.APP_VERSION}
