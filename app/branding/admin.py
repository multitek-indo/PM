from django.contrib import admin
from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'updated_at')
    readonly_fields = ('updated_at',)
    fields = ('company_name', 'updated_at')
    actions = None
    save_as = False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('branding.change_companyprofile')

    def has_view_permission(self, request, obj=None):
        return (request.user.has_perm('branding.view_companyprofile') or
                self.has_change_permission(request, obj))

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk=1)
