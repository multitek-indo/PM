import signal, time
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from maintenance.services import generate_orders
class Command(BaseCommand):
    help='Generator work order kalender tetap, setiap 5 menit.'
    def add_arguments(self,parser): parser.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        running=True
        def stop(*_):
            nonlocal running
            running=False
        signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
        while running:
            close_old_connections()
            try:
                count=generate_orders()
                self.stdout.write(f'Scheduler OK: {count} work order baru.'); self.stdout.flush()
            except Exception as exc:
                self.stderr.write(f'Scheduler gagal: {type(exc).__name__}; periksa database / log.'); self.stderr.flush()
                if options['once']: raise
            finally: close_old_connections()
            if options['once']: break
            for _ in range(300):
                if not running: break
                time.sleep(1)
