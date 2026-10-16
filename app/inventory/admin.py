"""Read-only evidence in Django admin. Stock writes go via audited mobile pages."""
from django.contrib import admin
from .models import Part, PartRequest, Stocktake, StocktakeLine, StockMovement


class ReadOnlyInventory(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


@admin.register(Part)
class PartAdmin(ReadOnlyInventory):
    list_display = ('sku','name','unit','current_qty','min_qty','location','active')
    search_fields = ('sku','name','machine_type')


@admin.register(PartRequest)
class PartRequestAdmin(ReadOnlyInventory):
    list_display = ('id','part','quantity','status','requested_by','created_at')


@admin.register(Stocktake)
class StocktakeAdmin(ReadOnlyInventory):
    list_display = ('id','title','status','created_by','created_at','posted_at')


@admin.register(StocktakeLine)
class StocktakeLineAdmin(ReadOnlyInventory):
    list_display = ('stocktake','part','book_qty','counted_qty')


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyInventory):
    list_display = ('created_at','part','kind','qty_delta','before_qty','after_qty','actor')
