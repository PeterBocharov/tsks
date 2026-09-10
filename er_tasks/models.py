from django.db import models
from django.utils import timezone


class Task(models.Model):
    eva_id = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=64, unique=True, db_index=True)
    url = models.URLField(max_length=512)
    project_code = models.CharField(max_length=64, db_index=True)
    project_name = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=512)
    text = models.TextField(blank=True)
    status = models.CharField(max_length=128, db_index=True)
    status_code = models.CharField(max_length=64, blank=True)
    status_type = models.CharField(max_length=32, blank=True, db_index=True)
    request_type = models.CharField(max_length=255, blank=True, db_index=True)
    epic = models.CharField(max_length=255, blank=True)
    tags = models.TextField(blank=True)
    assets = models.TextField(blank=True)
    components = models.TextField(blank=True)
    workflow_name = models.CharField(max_length=255, blank=True)
    workflow_code = models.CharField(max_length=64, blank=True)
    author_name = models.CharField(max_length=255, blank=True)
    author_login = models.CharField(max_length=255, blank=True)
    owner_name = models.CharField(max_length=255, blank=True)
    responsible_name = models.CharField(max_length=255, blank=True, db_index=True)
    responsible_login = models.CharField(max_length=255, blank=True)
    modified_by_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(db_index=True)
    modified_at = models.DateTimeField(db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_alarm = models.DateTimeField(null=True, blank=True)
    parent_task_id = models.CharField(max_length=128, blank=True)
    created_via = models.CharField(max_length=32, blank=True, db_index=True)
    labor_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment_count = models.PositiveIntegerField(default=0)
    synced_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-modified_at"]

    def __str__(self):
        return self.code

    @property
    def is_open(self):
        if self.status_type:
            return self.status_type.upper() != "CLOSED"
        return self.closed_at is None


class Comment(models.Model):
    eva_id = models.CharField(max_length=128, unique=True)
    task = models.ForeignKey(Task, related_name="comments", on_delete=models.CASCADE)
    created_at = models.DateTimeField(db_index=True)
    author_name = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)
    log_level = models.IntegerField(default=0)
    private = models.BooleanField(default=False)
    operation = models.CharField(max_length=64, blank=True, db_index=True)
    parsed_status = models.CharField(max_length=255, blank=True)
    waiting_for_person = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.eva_id


class TimeEntry(models.Model):
    eva_id = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=64, blank=True)
    task = models.ForeignKey(Task, related_name="time_entries", on_delete=models.CASCADE)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    owner_name = models.CharField(max_length=255, blank=True, db_index=True)
    owner_login = models.CharField(max_length=255, blank=True)
    minutes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    history_type = models.CharField(max_length=32, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-registered_at"]

    def __str__(self):
        return self.code or self.eva_id


class SyncState(models.Model):
    project_code = models.CharField(max_length=64, unique=True)
    last_modified_watermark = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    running = models.BooleanField(default=False)
    last_ok = models.BooleanField(default=True)
    last_error = models.TextField(blank=True)
    tasks_upserted = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.project_code
