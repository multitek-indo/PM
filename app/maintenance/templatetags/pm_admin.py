from django import template
register = template.Library()
LABELS = {'Machine':'Master mesin','Plan':'Jadwal preventive maintenance','WorkOrder':'Riwayat work order','AuditEvent':'Jejak aktivitas','SchedulerState':'Status penjadwalan','User':'Pengguna','Group':'Grup & hak akses'}
HELP = {'Machine':'Kelola identitas mesin, lokasi, serial number, dan status pemeliharaan.','Plan':'Atur interval, checklist pemeriksaan, tanggal jatuh tempo, dan teknisi.','WorkOrder':'Telusuri pekerjaan dan status persetujuan. Riwayat ini hanya-baca.','AuditEvent':'Lihat siapa melakukan tindakan dan kapan. Tidak dapat diubah dari menu ini.','SchedulerState':'Periksa waktu scheduler terakhir berjalan dan jumlah pekerjaan dibuat.','User':'Kelola akun teknisi, supervisor, dan akses administrasi.','Group':'Atur pengelompokan izin. Tinjau dampaknya sebelum mengubah.'}
@register.filter
def pm_model_label(model): return LABELS.get(model.get('object_name'),model.get('name','Menu'))
@register.filter
def pm_model_help(model): return HELP.get(model.get('object_name'),'Kelola data sesuai hak akses akun Anda.')
@register.filter
def pm_model_initial(model): return {'Machine':'M','Plan':'PM','WorkOrder':'WO','AuditEvent':'A','SchedulerState':'S','User':'U','Group':'G'}.get(model.get('object_name'),'M')
