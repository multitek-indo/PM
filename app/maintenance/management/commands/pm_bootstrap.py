import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        User=get_user_model()
        password=os.environ.get('PM_ADMIN_PASSWORD','')
        if not password: raise CommandError('Password bootstrap tidak tersedia.')
        if User.objects.filter(username='admin').exists(): raise CommandError('Admin sudah ada; password tidak akan ditimpa.')
        validate_password(password)
        User.objects.create_superuser(username='admin',password=password,email='')
        tech,_=Group.objects.get_or_create(name='Teknisi PM')
        group,_=Group.objects.get_or_create(name='Supervisor PM')
        perms=Permission.objects.filter(content_type__app_label='maintenance').exclude(codename__in=['add_workorder','change_workorder','delete_workorder','add_auditevent','change_auditevent','delete_auditevent','add_schedulerstate','change_schedulerstate','delete_schedulerstate'])
        group.permissions.set(perms)
        self.stdout.write('Admin dan grup PM dibuat. Password tidak dicetak dalam log.')
