from django.contrib import admin

from .models import Comment, SyncState, Task, TimeEntry


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "status",
        "status_type",
        "request_type",
        "responsible_name",
        "created_via",
        "created_at",
        "closed_at",
    )
    list_filter = ("status_type", "created_via", "request_type", "project_code")
    search_fields = ("code", "name", "author_name", "responsible_name")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("eva_id", "task", "operation", "author_name", "created_at")
    list_filter = ("operation",)
    search_fields = ("text", "author_name", "task__code")


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ("code", "task", "owner_name", "minutes", "start_at")
    search_fields = ("code", "owner_name", "task__code")


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = (
        "project_code",
        "running",
        "last_ok",
        "tasks_upserted",
        "last_modified_watermark",
        "last_run_at",
    )
    fields = (
        "project_code",
        "last_modified_watermark",
        "running",
        "last_ok",
        "last_error",
        "tasks_upserted",
        "last_run_at",
    )
    readonly_fields = ("running", "last_ok", "last_error", "tasks_upserted", "last_run_at")
