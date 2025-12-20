import PrusaLinkPy

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F

from printers.models import Printers
from printers.utils import map_printer_status


class Command(BaseCommand):
    help = "Poll printers and update DB"

    def handle(self, *args, **options):
        now = timezone.now()

        for printer in Printers.objects.all():

        try:
            client = PrusaLinkPy.PrusaLinkPy(printer.host, api_key=printer.api_key)

            resp = client.get_status()
            resp.raise_for_status()  # raises for HTTP 4xx/5xx

            status_json = resp.json()
            raw_state = status_json.get("printer", {}).get("state")
            job_info  = status_json.get("job", {}) or {}
            job_id = str(job_info.get("id") or "")


            if raw_state is not None:
                status = map_printer_status(raw_state)
        
            if status is "printing" and job_id != (printer.last_job_id or ""):
                Printers.objects.filter(slug=printer.slug).update(
                    total_print_count=F("total_print_count") + 1,
                    last_job_id=job_id
                )
                # sync the in-memory object if you need it
                printer.refresh_from_db(fields=["total_print_count", "last_job_id"])
        except:
            # if it fails, it fails
            pass