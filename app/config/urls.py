from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from maintenance import views
admin.site.site_header = 'Multitek PM - Administrasi'
admin.site.site_title = 'Multitek PM'
admin.site.index_title = 'Pusat administrasi'
admin.site.index_template = 'admin/pm_index.html'
urlpatterns = [
    path('api/time/', views.server_time, name='server_time'),
    path('machines/template.xlsx', views.machine_template_excel, name='machine_template_excel'),
    path('healthz', views.healthz, name='healthz'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password/', auth_views.PasswordChangeView.as_view(template_name='registration/password.html', success_url='/'), name='password_change'),
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('machines/', views.machines, name='machines'),
    path('machines/import/', views.import_machines, name='import_machines'),
    path('machines/template.csv', views.machine_template, name='machine_template'),
    path('machines/<uuid:uid>/', views.machine_detail, name='machine_detail'),
    path('machines/<uuid:uid>/qr.svg', views.machine_qr, name='machine_qr'),
    path('orders/', views.orders, name='orders'),
    path('orders/export.csv', views.export_orders, name='export_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
]

# BEGIN SPAREPART PHOTO 0.3.1
from spareparts import views as spareparts_views
urlpatterns += [
    path('orders/<int:pk>/spareparts/upload/', spareparts_views.upload_photo, name='sparepart_upload_photo'),
    path('spareparts/<int:photo_id>/photo/', spareparts_views.view_photo, name='sparepart_view_photo'),
]
# END SPAREPART PHOTO 0.3.1

# BEGIN INVENTORY 0.4.0
from inventory import views as inventory_views
urlpatterns += [
    path('inventory/', inventory_views.overview, name='inventory_overview'),
    path('inventory/parts/new/', inventory_views.add_part, name='inventory_add_part'),
    path('inventory/parts/<int:pk>/edit/', inventory_views.edit_part, name='inventory_edit_part'),
    path('inventory/movement/', inventory_views.movement, name='inventory_movement'),
    path('inventory/requests/', inventory_views.requests, name='inventory_requests'),
    path('inventory/requests/new/', inventory_views.request_part, name='inventory_request_new'),
    path('inventory/requests/<int:pk>/decide/', inventory_views.request_decide, name='inventory_request_decide'),
    path('inventory/requests/<int:pk>/issue/', inventory_views.request_issue, name='inventory_request_issue'),
    path('inventory/opname/', inventory_views.stocktakes, name='inventory_stocktakes'),
    path('inventory/opname/new/', inventory_views.stocktake_new, name='inventory_stocktake_new'),
    path('inventory/opname/<int:pk>/', inventory_views.stocktake_detail, name='inventory_stocktake_detail'),
    path('inventory/opname/<int:pk>/count/<int:line_id>/', inventory_views.stocktake_count, name='inventory_stocktake_count'),
    path('inventory/opname/<int:pk>/post/', inventory_views.stocktake_post, name='inventory_stocktake_post'),
    path('inventory/opname/<int:pk>/cancel/', inventory_views.stocktake_cancel, name='inventory_stocktake_cancel'),
]
# END INVENTORY 0.4.0
