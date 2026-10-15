from django.contrib import admin
from .models import Machine, Plan, WorkOrder, AuditEvent, SchedulerState

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('code','name','category','site','line','active')
    list_filter = ('active','site','category')
    search_fields = ('code','name','serial','line')
    readonly_fields = ('uid','created_at')
    list_per_page = 50

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('machine','title','interval_days','next_due','assigned_to','active')
    list_filter = ('active','machine__site')
    search_fields = ('machine__code','title')
    autocomplete_fields = ('machine','assigned_to')
    list_select_related = ('machine','assigned_to')

class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False
    def has_change_permission(self,request,obj=None): return False
    def get_readonly_fields(self,request,obj=None): return [f.name for f in self.model._meta.fields]

@admin.register(WorkOrder)
class WorkOrderAdmin(ReadOnlyAdmin):
    list_display = ('id','plan','due_date','status','assigned_to')
    list_filter = ('status','due_date')
    search_fields = ('plan__machine__code','title')
    list_select_related = ('plan__machine','assigned_to')

@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ('created_at','order','actor','action')
    list_filter = ('action',)
    list_select_related = ('order','actor')

admin.site.register(SchedulerState,ReadOnlyAdmin)
