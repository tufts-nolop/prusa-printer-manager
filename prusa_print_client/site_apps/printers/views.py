import json
import os
from pathlib import Path
import tempfile
import PrusaLinkPy

from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_POST 
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.admin.views.decorators import staff_member_required
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


########## Helper funcs ##########

def pause_current_print(client):
    try:
        resp = client.pause_print()
        return resp
    # TODO: add proper err handling
    except requests.RequestException as e:
        print("Error pausing print:", e)


def resume_current_print(client):
    try:
        resp = client.resume_print()
        return resp
    # TODO: add proper err handling here too
    except requests.RequestException as e:
        print("Error resuming print:", e)


def stop_current_print(client):
    try:
        resp = client.stop_print()
        return resp
    except requests.RequestException as e:
        print("Error stopping print:", e) # TODO: change this as well


def remote_file_exists_usb(client, remote_path: str) -> bool:
    host = getattr(client, "host", None) or getattr(client, "_host", None)
    api_key = getattr(client, "api_key", None) or getattr(client, "_api_key", None)
    if not host or not api_key:
        raise ValueError("Couldn't read host/api_key off PrusaLinkPy client")

    rp = (remote_path or "").strip().strip("/")  # "PRINT_QUEUE/3DBenchy.bgcode"
    url = f"http://{host}/api/v1/files/usb/{rp}"

    r = requests.get(url, headers={"X-Api-Key": api_key, "Accept": "application/json"}, timeout=10)

    if r.status_code == 200:
        return True
    if r.status_code == 404:
        return False

    # anything else is useful to see (403, 401, 500)
    print("exists check failed:", r.status_code, r.text[:200])
    return False


########## Django views ##########

class PrintersListView(ListView):
    model = Printers
    template_name = "printer_dashboard.html"

    def get_queryset(self):
        qs = super().get_queryset()
        objs = list(qs)

        # used for sorting printers from p1, p2, p3, etc. bc i entered them in the db at different times
        def sort_key(o):
            name = (o.name or "").strip()
            m = re.search(r"(\d+)$", name)
            num = int(m.group(1)) if m else 10**9  # non-matching go last
            return (num, name.lower())

        objs.sort(key=sort_key)
        return objs

@ensure_csrf_cookie
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

    printer_objs = Printers.objects.all()

    for printer in printer_objs:
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
        status_resp = printer_actual.get_status()
        job_resp = printer_actual.get_job()
    except:
        return JsonResponse(
                {
                    "error": "Printer unavailable"
                },
                status=502,
            )

    # resp = printer_actual.get_status()
    status = status_resp.json()

    printer_info = status.get("printer", {})
    more_job_info     = status.get("job", {})

   # bc there could be a good ststus code but no active job on the printer
   # jankass solution but it works so whatever
    usage_mm = None
    usage_g = None
    usage_cm3 = None
    if job_resp.status_code == 204 or not job_resp.content.strip():
        job_info = None
    else:
        job_resp.raise_for_status()  # will only raise on 4xx/5xx
        job_info = job_resp.json()
        usage_mm, usage_g, usage_cm3 = get_filament_usage_from_running_job(printer_djobj, printer_info, job_info)
    # resp.raise_for_status()
    

    dt = printer_djobj.last_maintenance
    dt = timezone.localtime(dt)  # optional: convert to local time?

    nozzle_temp    = printer_info.get("temp_nozzle", 0)        # °C
    bed_temp       = printer_info.get("temp_bed", 0)           # °C
    progress       = more_job_info.get("progress", 0)               # percent (0–100)
    time_remaining = more_job_info.get("time_remaining", 0)        # seconds
    curr_status    = map_printer_status(printer_info["state"])
    date_string    = date_format(dt, "Y-m-d")

    

    payload = model_to_dict(printer_djobj)
    payload["nozzle_temp"]      = nozzle_temp
    payload["bed_temp"]         = bed_temp
    payload["progress"]         = progress
    payload["curr_status"]      = curr_status
    payload["last_maintenance"] = date_string

    # print(time_remaining)
    if (time_remaining / 60) > 100:
        payload["time_remaining"] = round(((time_remaining / 60) / 60)) # convert to hours if big
        payload["time_units"]     = " hours"
    else:
        payload["time_remaining"] = (round(time_remaining / 60)) # convert to min
        payload["time_units"]     = " minutes"    
        
    if usage_mm is not None:
        payload["usage_mm"] = usage_mm
    if usage_g is not None:
        payload["usage_g"] = usage_g
    if usage_cm3 is not None:
        payload["usage_cm3"] = usage_cm3

    if request.user.is_superuser:
        try:
            succ_rate = round(float(printer_djobj.successful_prints / printer_djobj.total_print_count), 2)
        except:
            succ_rate = ""
        payload["success_rate"] = succ_rate
        payload["total_prints"] = printer_djobj.total_print_count
        payload["total_filament_usage_mm"] = printer_djobj.filament_usage_mm
        payload["total_filament_usage_cm3"] = printer_djobj.filament_usage_cm3
        payload["total_filament_usage_g"] = printer_djobj.filament_usage_g

    return JsonResponse(payload, safe=False)

@require_POST
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
        remote_path = f"{remote_dir}/{uploaded_file.name}"

        if (remote_file_exists_usb(printer_actual, remote_path)):
            data = {
                "success": False,
                'status': 404,
                'message': f"The file already exists at {remote_path}",
            }
            return JsonResponse(data)

        # NO AUTOSTART, THEY MUST BE AT THE PRINTER
        if request.user.is_superuser:
            resp = printer_actual.put_gcode(
                tmp_path,
                remote_path,
                printAfterUpload=True,
                overwrite=True,
            )
        else:
            resp = printer_actual.put_gcode(
                tmp_path,
                remote_path,
                printAfterUpload=False,
                overwrite=True,
            )



        stat_code = int(resp.status_code)
        if stat_code != 200:
            if stat_code == 500:
                data = {
                    "success": False,
                    'status': stat_code,
                    'message': "Printer upload failed, contact staff for assistance",
                }
                return JsonResponse(data)
            if stat_code == 507:
                data = {
                    "success": False,
                    'status': stat_code,
                    'message': "Failed to write to location, check for inserted USB drive or swap it for a different one",
                }
                return JsonResponse(data)

        print(filament_mm)
        print(filament_g)
        print(filament_cm3)
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
                "success": True,
                "remote_path": str(remote_path),
            }
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except PermissionError:
                pass
 
@staff_member_required           
def printer_commands_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    
    if request.user.is_superuser:
        printer_djobj = get_object_or_404(Printers.objects.filter(slug=data["slug"]))
        printer_action = data["action"]
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

        if printer_action == "stop":
            resp = stop_current_print(printer_actual)
        elif printer_action == "resume":
            resp = resume_current_print(printer_actual)
        else:
            resp = pause_current_print(printer_actual)
            
        if resp.status_code and resp.text:
            return JsonResponse(
                {
                    "error": f"Printer action {printer_action.upper()}",
                    "printer_status_code": resp.status_code,
                    "printer_body": resp.text,
                },
            )

@staff_member_required
def printer_notes_api(request):           
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    
    if request.user.is_superuser:
        printer_djobj = get_object_or_404(Printers.objects.filter(slug=data["slug"]))
        new_note = str(data["new_note"])

        printer_djobj.staff_notes = new_note
        try:
            printer_djobj.save()
            return JsonResponse(
                    {
                        "success": "Note saved to database"
                    },
                    status=502,
                )
        except:
            return JsonResponse(
                    {
                        "error": "Error saving note to database"
                    },
                    status=502,
                )
