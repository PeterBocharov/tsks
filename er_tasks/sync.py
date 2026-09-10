from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .eva_client import EvaClient
from .models import Comment, SyncState, Task, TimeEntry
from .parsers import extract_comments, extract_task, extract_time_entries


class SyncAlreadyRunning(Exception):
    pass


class SyncConfigError(Exception):
    pass


def _watermark_str(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%dT%H:%M:%S")


def run_sync(client=None, project_code=None, batch_days=None):
    started = timezone.now()
    project_code = project_code or settings.EVA_PROJECT_CODE
    batch_days = batch_days if batch_days is not None else settings.EVA_BATCH_DAYS
    if not (settings.EVA_TOKEN or (client and client.token)):
        raise SyncConfigError("EVA_TOKEN is not set")

    with transaction.atomic():
        try:
            state = SyncState.objects.select_for_update().get(project_code=project_code)
        except SyncState.DoesNotExist as exc:
            raise SyncConfigError(
                f"SyncState for project {project_code!r} is missing; "
                "create it in admin and set last_modified_watermark"
            ) from exc
        if not state.last_modified_watermark:
            raise SyncConfigError(
                f"SyncState for project {project_code!r} has no last_modified_watermark; "
                "set the starting watermark in admin"
            )
        if state.running and state.last_run_at:
            age = timezone.now() - state.last_run_at
            if age < timedelta(minutes=30):
                raise SyncAlreadyRunning("sync already running")
        state.running = True
        state.last_run_at = timezone.now()
        state.last_error = ""
        state.save(update_fields=["running", "last_run_at", "last_error"])

    upserted = 0
    error = ""
    watermark = state.last_modified_watermark
    try:
        client = client or EvaClient()
        project = client.get_project(project_code)
        project_id = project["id"]
        project_name = project.get("name") or project_code

        cursor = watermark - timedelta(minutes=2)
        now = timezone.now()
        max_modified = watermark
        base_url = settings.EVA_TASK_BASE_URL
        while cursor < now:
            window_end = min(cursor + timedelta(days=batch_days), now)
            modified_from = _watermark_str(cursor)
            modified_to = _watermark_str(window_end)
            print(f'modified_from - {modified_from}  modified_to - {modified_to}')
            raw_tasks = client.list_tasks(project_id, modified_from, modified_to)
            for raw in raw_tasks:
                task_data = extract_task(raw, project_name, project_code, base_url)
                comments, rating = extract_comments(raw)
                time_rows, total_minutes = extract_time_entries(raw)
                task_data["rating"] = rating
                task_data["labor_hours"] = (Decimal(total_minutes) / Decimal(60)).quantize(
                    Decimal("0.01")
                )
                task_data["synced_at"] = timezone.now()
                eva_id = task_data.pop("eva_id")
                code = task_data["code"]
                task, _ = Task.objects.update_or_create(
                    eva_id=eva_id,
                    defaults=task_data,
                )
                if task.code != code:
                    task.code = code
                    task.save(update_fields=["code"])

                comment_ids = []
                for row in comments:
                    cid = row.pop("eva_id")
                    comment_ids.append(cid)
                    Comment.objects.update_or_create(
                        eva_id=cid, defaults={"task": task, **row}
                    )
                if comment_ids:
                    Comment.objects.filter(task=task).exclude(eva_id__in=comment_ids).delete()
                else:
                    Comment.objects.filter(task=task).delete()

                time_ids = []
                for row in time_rows:
                    tid = row.pop("eva_id")
                    time_ids.append(tid)
                    TimeEntry.objects.update_or_create(
                        eva_id=tid, defaults={"task": task, **row}
                    )
                if time_ids:
                    TimeEntry.objects.filter(task=task).exclude(eva_id__in=time_ids).delete()
                else:
                    TimeEntry.objects.filter(task=task).delete()

                upserted += 1
                if task.modified_at and (max_modified is None or task.modified_at > max_modified):
                    max_modified = task.modified_at

            # Advance past empty windows so a restart continues the backfill.
            advance_to = window_end
            if max_modified and max_modified > advance_to:
                advance_to = max_modified
            state.last_modified_watermark = advance_to
            state.save(update_fields=["last_modified_watermark"])
            cursor = window_end

        watermark = state.last_modified_watermark
        state.last_ok = True
        state.tasks_upserted = upserted
        state.last_error = ""
    except Exception as exc:
        error = str(exc)
        state.last_ok = False
        state.last_error = error
        raise
    finally:
        state.running = False
        state.last_run_at = timezone.now()
        state.save()

    duration = (timezone.now() - started).total_seconds()
    return {
        "ok": True,
        "tasks_upserted": upserted,
        "watermark": watermark.isoformat() if watermark else None,
        "duration_sec": round(duration, 2),
        "error": "",
        "project_code": project_code,
    }
