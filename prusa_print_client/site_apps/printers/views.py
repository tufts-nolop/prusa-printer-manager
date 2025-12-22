import json
import os
from pathlib import Path
import tempfile
import PrusaLinkPy

from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, render
from django.views.generic.list import ListView
from django.forms.models import model_to_dict
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils.formats import date_format
from django.utils import timezone
import requests

from .utils import *
from .models import Printers, PendingJobUsage


########## Django views ##########

class PrintersListView(ListView):
    model = Printers
    template_name = "printer_dashboard.html"


def get_printer(request, slug):
    printer = get_object_or_404(Printers.objects.filter(slug=slug))

    return render(
        request,
        "single_printer.html",
        {"printer": printer},
    )



########## AJAX functions/API calls ##########

def printers_status_api(request):
    data = []

    for printer in Printers.objects.all():
        status = "offline"  # default if anything goes wrong

        try:
            client = PrusaLinkPy.PrusaLinkPy(printer.host, api_key=printer.api_key)

            resp = client.get_status()
            resp.raise_for_status()  # raises for HTTP 4xx/5xx

            status_json = resp.json()
            raw_state = status_json.get("printer", {}).get("state")

            if raw_state is not None:
                status = map_printer_status(raw_state)
            else:
                # if for some reason there's no state, treat as busy/error-ish
                status = "busy"

        except (requests.exceptions.RequestException, ValueError, KeyError) as e:
            # Printer unreachable, bad response, or JSON shape not as expected
            # status stays "offline"
            # you can log e here if you want
            pass

        data.append({
            "slug": printer.slug,
            "status": status,
        })

    return JsonResponse(data, safe=False)


@require_POST
def individual_printer_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    
    printer_djobj = get_object_or_404(Printers.objects.filter(slug=data["slug"]))
    printer_actual = PrusaLinkPy.PrusaLinkPy(str(printer_djobj.host), str(printer_djobj.api_key))
    try:
        resp = printer_actual.get_status()
    except:
        return JsonResponse(
                {
                    "error": "Printer unavailable"
                },
                status=502,
            )

    # resp = printer_actual.get_status()
    status = resp.json()

    printer_info = status.get("printer", {})
    job_info     = status.get("job", {})

    dt = printer_djobj.last_maintenance
    dt = timezone.localtime(dt)  # optional: convert to local time?

    nozzle_temp    = printer_info.get("temp_nozzle", 0)        # °C
    bed_temp       = printer_info.get("temp_bed", 0)           # °C
    progress       = job_info.get("progress", 0)               # percent (0–100)
    time_remaining = job_info.get("time_remaining", 0)        # seconds
    curr_status    = map_printer_status(printer_info["state"])
    date_string    = date_format(dt, "Y-m-d")
    usage_mm, usage_g, usage_cm3, _ = get_filament_usage_from_job(printer_djobj, job_info)
    

    payload = model_to_dict(printer_djobj)
    payload["nozzle_temp"]      = nozzle_temp
    payload["bed_temp"]         = bed_temp
    payload["progress"]         = progress
    payload["curr_status"]      = curr_status
    payload["last_maintenance"] = date_string

    if (time_remaining / 60) > 100:
        payload["time_remaining"] = round(((time_remaining / 60) / 60), 2) # convert to hours if big
        payload["time_units"]     = " hours"
    else:
        payload["time_remaining"] = (round(time_remaining / 60), 2) # convert to min
        payload["time_units"]     = " minutes"    
        
    if usage_mm:
        payload["usage_mm"] = usage_mm
    if usage_g:
        payload["usage_g"] = usage_g
    if usage_cm3:
        payload["usage_cm3"] = usage_cm3

    if request.user.is_superuser:
        payload["success_rate"] = round(float(printer_djobj.successful_prints / printer_djobj.total_print_count), 2)
        payload["total_prints"] = printer_djobj.total_print_count
        payload["total_filament_usage_mm"] = printer_djobj.filament_usage_mm
        payload["total_filament_usage_cm3"] = printer_djobj.filament_usage_cm3
        payload["total_filament_usage_g"] = printer_djobj.filament_usage_g

    return JsonResponse(payload, safe=False)


def upload_bgcode_api(request):
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    slug = request.POST.get("slug")
    printer_djobj = get_object_or_404(Printers.objects.filter(slug=slug))
    printer_actual = PrusaLinkPy.PrusaLinkPy(str(printer_djobj.host), str(printer_djobj.api_key))
    
    usage = get_filament_usage_from_file(uploaded_file)
    filament_mm = usage.get("mm")
    filament_g = usage.get("g")
    filament_cm3 = usage.get("cm3")
    


    # Write to a temporary file ONLY so PrusaLinkPy can read it
    suffix = Path(uploaded_file.name).suffix or ".bgcode"
    tmp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # remote path
        remote_dir = "PRINT_QUEUE"
        remote_name = uploaded_file.name
        remote_path = f"{remote_dir}/{remote_name}"

        # NO AUTOSTART, THEY MUST BE AT THE PRINTER
        resp = printer_actual.put_gcode(
            tmp_path,
            remote_path,
            printAfterUpload=False,
            overwrite=True,
        )

        if resp.status_code != 200:
            return JsonResponse(
                {
                    "error": "Printer upload failed",
                    "printer_status_code": resp.status_code,
                    "printer_body": resp.text,
                },
                status=502,
            )
        
        if filament_mm is not None or filament_g is not None or filament_cm3 is not None:
            PendingJobUsage.objects.create(
                printer=printer_djobj,
                remote_path=remote_path,
                filament_mm=filament_mm,
                filament_g=filament_g,
                filament_cm3=filament_cm3,
            )

        return JsonResponse(
            {
                "ok": True,
                "filename": uploaded_file.name,
                "remote_path": remote_path,
            }
        )
        
        

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass