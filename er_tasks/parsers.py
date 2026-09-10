import re
from datetime import datetime

from django.utils.dateparse import parse_datetime
from django.utils import timezone

TPLIST = [
    "Пчелин Василий Андреевич",
    "Кочергин Анатолий Григорьевич",
    "Коробейников Антон Павлович",
    "Федотов Андрей Васильевич",
    "Кузнецов Дмитрий Владиславович",
    "Потапова-Раменская Ольга Юрьевна",
    "Слободенюк Валерий Валериевич",
    "Бондуривский Сергей Михайлович",
]

STATUS_CHANGE_RE = re.compile(r"^Статус изменен на\s+([^,]+),")
ASSIGN_RE = re.compile(r"^Задача назначена на\s+([^,]+?),")
WAITING_RE = re.compile(r"^Ждем ответа:.*?➔\s*<ins>([^<]+)</ins>", re.DOTALL)
RATING_RE = re.compile(r"Оценка:.*?➔\s*<ins>(\d+)</ins>", re.DOTALL)
RESOLUTION_PREFIX = "Резолюция: <del>Не указано</del> ➔ <ins>Готово</ins>"


def parse_eva_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
        if dt is None:
            cleaned = str(value).replace("T", " ").split(".")[0]
            if "+" in cleaned:
                cleaned = cleaned.split("+")[0]
            try:
                dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def join_names(items):
    if not items:
        return ""
    return " ".join((item.get("name") or "").strip() for item in items).strip()


def extract_status(text, task_status=""):
    text = text or ""
    result = ""
    result_type = ""

    match = STATUS_CHANGE_RE.search(text)
    if match:
        result = match.group(1).strip()
        result_type = "status_change"
        if "Пауза" in result:
            result_type = "paused"

    match2 = ASSIGN_RE.search(text)
    if match2:
        result = match2.group(1).strip()
        result_type = "assignment"

    waiting = WAITING_RE.search(text)
    if waiting:
        result = waiting.group(1).strip()
        if result == "Не указано":
            result = ""
        result_type = "waiting_for"

    if text == "Создано":
        return "", "created"
    if text == "Задача закрыта":
        return "", "closed"
    if text in {"Работа по задаче окончена", "Задача завершена"}:
        return "", "work_finished"
    if text.startswith(RESOLUTION_PREFIX):
        return task_status or "Готово", "resolution"
    if text == "Сделана запись о работе":
        return "", "work_logged"
    if text.startswith("Установлена связь"):
        return "", "linked"
    if text.startswith("SimpleLogic: waiting_for"):
        return "", "waiting_for"
    if text.startswith("Продолжите работу"):
        return "", "paused"
    if not result_type and text.startswith("Статус изменен на"):
        result_type = "status_change"

    return result, result_type


def infer_created_via(task_text, author_name):
    text = task_text or "НЕТ"
    if text[:27] == '<table class="mail-header">':
        return "email"
    portal_like = text[:11] in {"<p data-id=", "НЕТ"}
    if portal_like and author_name in TPLIST:
        return "portal_by_tp"
    if portal_like:
        return "portal"
    return ""


def extract_task(task, project_name, project_code, task_base_url):
    status_obj = task.get("status") or {}
    author = task.get("cmf_author") or {}
    responsible = task.get("responsible") or {}
    owner = task.get("cmf_owner") or {}
    modified_by = task.get("cmf_modified_by") or {}
    scheme = task.get("scheme_wf") or {}
    epic = task.get("epic") or {}
    request_type = task.get("request_type") or {}
    code = task.get("code") or ""
    task_text = task.get("text") or "НЕТ"
    author_name = author.get("name") or ""

    return {
        "eva_id": task["id"],
        "code": code,
        "url": f"{task_base_url.rstrip('/')}/{code}",
        "project_code": project_code,
        "project_name": project_name,
        "name": task.get("name") or "",
        "text": task.get("text") or "",
        "status": status_obj.get("name") or "",
        "status_code": status_obj.get("code") or "",
        "status_type": (
            status_obj.get("status_type")
            or task.get("cache_status_type")
            or ""
        ),
        "request_type": request_type.get("name") or "",
        "epic": (epic.get("name") if isinstance(epic, dict) else "") or "",
        "tags": join_names(task.get("tags") or []),
        "assets": join_names(task.get("assets") or []),
        "components": join_names(task.get("components") or []),
        "workflow_name": scheme.get("name") or "",
        "workflow_code": scheme.get("code") or "",
        "author_name": author_name or "Автор не найден или удален",
        "author_login": author.get("login") or "",
        "owner_name": owner.get("name") or "",
        "responsible_name": responsible.get("name") or "Исполнитель не назначен",
        "responsible_login": responsible.get("login") or "",
        "modified_by_name": modified_by.get("name") or "",
        "created_at": parse_eva_datetime(task.get("cmf_created_at")),
        "modified_at": parse_eva_datetime(task.get("cmf_modified_at")),
        "closed_at": parse_eva_datetime(task.get("status_closed_at") or None),
        "next_alarm": parse_eva_datetime((status_obj.get("next_alarm") or None)),
        "parent_task_id": task.get("parent_task_id") or "",
        "created_via": infer_created_via(task_text, author_name),
        "comment_count": len(task.get("comments") or []),
    }


def extract_comments(task):
    status_name = (task.get("status") or {}).get("name") or ""
    rating = None
    rows = []
    for comment in task.get("comments") or []:
        text = comment.get("text") or ""
        parsed, operation = extract_status(text, status_name)
        waiting = parsed if operation == "waiting_for" else ""
        rating_match = RATING_RE.search(text)
        if rating_match:
            rating = int(rating_match.group(1))
        rows.append(
            {
                "eva_id": comment["id"],
                "created_at": parse_eva_datetime(comment.get("cmf_created_at")),
                "author_name": comment.get("cache_cmf_author_name") or "",
                "text": text,
                "log_level": comment.get("log_level") or 0,
                "private": bool(comment.get("private")),
                "operation": operation,
                "parsed_status": parsed if operation != "waiting_for" else "",
                "waiting_for_person": waiting,
            }
        )
    return rows, rating


def extract_time_entries(task):
    rows = []
    total_minutes = 0
    for tt in task.get("timetracker_history") or []:
        minutes = tt.get("time_spent") or 0
        total_minutes += minutes
        owner = tt.get("cmf_owner") or {}
        rows.append(
            {
                "eva_id": tt["id"],
                "code": tt.get("code") or "",
                "start_at": parse_eva_datetime(tt.get("start_date")),
                "end_at": parse_eva_datetime(tt.get("end_date")),
                "registered_at": parse_eva_datetime(tt.get("cmf_created_at")),
                "owner_name": owner.get("name") or "",
                "owner_login": owner.get("login") or "",
                "minutes": minutes,
                "history_type": tt.get("history_type") or "",
                "comment": tt.get("text") or "",
            }
        )
    return rows, total_minutes
