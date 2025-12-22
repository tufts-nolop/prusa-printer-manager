import requests
import PrusaLinkPy

from django.core.management.base import BaseCommand
from django.db.models import F
from django.db import transaction

from printers.models import Printers
from printers.utils import *


class Command(BaseCommand):
    help = """Polls printers to increment their total print count, update total filament usage, etc. for collecting stats
                to better track the printers as they degrade"""

    def handle(self, *args, **options):

        for printer in Printers.objects.all():

            try:
        
                client = PrusaLinkPy.PrusaLinkPy(printer.host, api_key=printer.api_key)

                resp = client.get_status()
                resp.raise_for_status()  # raises for HTTP 4xx/5xx

                # grabbing the data
                status_json = resp.json()
                raw_state = status_json.get("printer", {}).get("state")
                job_info  = status_json.get("job", {}) or {}
                job_id = str(job_info.get("id") or "")

                ### updating total prints to date for each printer
                if raw_state is not None:
                    status = map_printer_status(raw_state)
            
                if status is "printing" and job_id != (printer.last_job_id or ""):
                    Printers.objects.filter(slug=printer.slug).update(
                        total_print_count=F("total_print_count") + 1,
                        last_job_id=job_id
                    )
                    # sync the in-memory object if you need it
                    printer.refresh_from_db(fields=["total_print_count", "last_job_id"])
                    
                    
                ### updating filament usage
                with transaction.atomic():
                    used_mm, used_g, used_cm3, pending = get_filament_usage_from_job(printer, job_info)
                    changed_fields = []

                    if used_mm:
                        printer.filament_usage_mm += used_mm
                        changed_fields.append("filament_usage_mm")
                    if used_g:
                        printer.filament_usage_g += used_g
                        changed_fields.append("filament_usage_g")
                    if used_cm3:
                        printer.filament_usage_cm3 += used_cm3
                        changed_fields.append("filament_usage_cm3")
                    if changed_fields:
                        printer.save(update_fields=changed_fields)
                    # remove pending usage so we don't double-count next cron run
                    if pending:
                        pending.delete()
                    
            except:
                # if it fails, it fails
                pass