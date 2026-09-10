from collections import defaultdict

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import Task, TimeEntry
from .parsers import TPLIST


def apply_filters(qs, params):
    date_from = params.get("from")
    date_to = params.get("to")
    request_type = params.get("request_type")
    assignee = params.get("assignee")
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if request_type:
        qs = qs.filter(request_type=request_type)
    if assignee:
        qs = qs.filter(responsible_name=assignee)
    return qs


def filter_choices():
    return {
        "request_types": list(
            Task.objects.exclude(request_type="")
            .order_by("request_type")
            .values_list("request_type", flat=True)
            .distinct()
        ),
        "assignees": list(
            Task.objects.exclude(responsible_name="")
            .order_by("responsible_name")
            .values_list("responsible_name", flat=True)
            .distinct()
        ),
    }


def volume(qs):
    created = list(
        qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    closed_qs = qs.filter(closed_at__isnull=False)
    closed = list(
        closed_qs.annotate(day=TruncDate("closed_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    open_count = qs.filter(closed_at__isnull=True).count()
    if qs.exclude(status_type="").exists():
        open_count = qs.exclude(status_type__iexact="CLOSED").count()
    return {
        "created": created,
        "closed": closed,
        "open_count": open_count,
        "total": qs.count(),
    }


AGING_BUCKETS = [
    ("0–1d", 0, 1),
    ("1–3d", 1, 3),
    ("3–7d", 3, 7),
    ("7–14d", 7, 14),
    ("14+d", 14, None),
]


def aging(qs):
    now = timezone.now()
    open_qs = qs.exclude(status_type__iexact="CLOSED")
    if not qs.exclude(status_type="").exists():
        open_qs = qs.filter(closed_at__isnull=True)

    buckets = {label: 0 for label, *_ in AGING_BUCKETS}
    by_assignee = defaultdict(lambda: {label: 0 for label, *_ in AGING_BUCKETS})
    by_status = defaultdict(int)
    rows = []
    for task in open_qs.only(
        "created_at", "responsible_name", "status", "code", "name", "url"
    ):
        days = max((now - task.created_at).total_seconds() / 86400, 0)
        label = "14+d"
        for name, low, high in AGING_BUCKETS:
            if high is None and days >= low:
                label = name
                break
            if high is not None and days >= low and days < high:
                label = name
                break
        buckets[label] += 1
        by_assignee[task.responsible_name or "—"][label] += 1
        by_status[task.status or "—"] += 1
        rows.append(task)
    return {
        "buckets": buckets,
        "by_assignee": dict(by_assignee),
        "by_status": dict(by_status),
        "open_tasks": rows[:200],
        "open_count": len(rows),
    }


def queues(qs):
    def grouped(field):
        return list(
            qs.exclude(**{f"{field}": ""})
            .values(field)
            .annotate(n=Count("id"))
            .order_by("-n")[:20]
        )

    return {
        "request_type": grouped("request_type"),
        "epic": grouped("epic"),
        "status": grouped("status"),
        "responsible_name": grouped("responsible_name"),
        "workflow_name": grouped("workflow_name"),
        "created_via": grouped("created_via"),
    }


def custom(qs):
    via = list(qs.values("created_via").annotate(n=Count("id")).order_by("-n"))
    tp_count = qs.filter(author_name__in=TPLIST).count()
    other_count = qs.exclude(author_name__in=TPLIST).count()
    rating = qs.exclude(rating__isnull=True).aggregate(avg=Avg("rating"), n=Count("id"))
    hours = list(
        TimeEntry.objects.filter(task__in=qs)
        .values("owner_name")
        .annotate(minutes=Sum("minutes"), n=Count("id"))
        .order_by("-minutes")[:20]
    )
    return {
        "created_via": via,
        "tp_count": tp_count,
        "other_authors": other_count,
        "rating_avg": rating["avg"],
        "rating_n": rating["n"],
        "hours_by_owner": hours,
    }
