import json
import secrets

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import analytics as stats
from .models import Task
from .sync import SyncAlreadyRunning, SyncConfigError, run_sync


def _sync_token_ok(request):
    expected = settings.SYNC_TOKEN or ""
    if not expected:
        return False
    header = request.headers.get("Authorization", "")
    token = ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    token = token or request.headers.get("X-Sync-Token", "")
    return secrets.compare_digest(token, expected)


# @csrf_exempt
# @require_POST
def sync_view(request):
    # if not _sync_token_ok(request):
    #     return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        result = run_sync()
    except SyncAlreadyRunning as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    except SyncConfigError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    return JsonResponse(result)


def _page(request, template, extra):
    qs = stats.apply_filters(Task.objects.all(), request.GET)
    ctx = {
        "filters": stats.filter_choices(),
        "params": request.GET,
        **extra(qs),
    }
    return render(request, template, ctx)


def volume(request):
    def extra(qs):
        data = stats.volume(qs)
        return {
            "volume": data,
            "created_json": json.dumps(
                [{"x": str(r["day"]), "y": r["n"]} for r in data["created"]],
                default=str,
            ),
            "closed_json": json.dumps(
                [{"x": str(r["day"]), "y": r["n"]} for r in data["closed"]],
                default=str,
            ),
        }

    return _page(request, "er_tasks/volume.html", extra)


def aging(request):
    def extra(qs):
        data = stats.aging(qs)
        return {
            "aging": data,
            "buckets_json": json.dumps(
                [{"x": k, "y": v} for k, v in data["buckets"].items()]
            ),
        }

    return _page(request, "er_tasks/aging.html", extra)


def queues(request):
    def extra(qs):
        data = stats.queues(qs)
        return {"queues": data}

    return _page(request, "er_tasks/queues.html", extra)


def custom(request):
    def extra(qs):
        data = stats.custom(qs)
        return {"custom": data}

    return _page(request, "er_tasks/custom.html", extra)
