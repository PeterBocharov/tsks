from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from er_tasks.models import SyncState, Task
from er_tasks.sync import run_sync


SAMPLE_PROJECT = {"id": "CmfProject:1", "name": "HelpDesk", "code": "NS"}
SAMPLE_TASK = {
    "id": "CmfTask:d4838480-7e7c-11f1-a843-0242ac110002",
    "code": "NS-27278",
    "name": "Переустановка ОС",
    "text": "<p data-id=\"naHIiA8k\">hello</p>",
    "cmf_created_at": "2026-07-13T08:39:34.622063+03:00",
    "cmf_modified_at": "2026-09-08T16:24:29.970628+03:00",
    "status_closed_at": "2026-09-08T16:24:28.852691+03:00",
    "cmf_author": {"name": "Слободенюк Валерий Валериевич", "login": "v.slobodenyuk@nord.local"},
    "cmf_owner": {"name": "Слободенюк Валерий Валериевич"},
    "cmf_modified_by": {"name": "Пчелин Василий Андреевич"},
    "responsible": {"name": "Пчелин Василий Андреевич", "login": "v.pchelin@nord.local"},
    "request_type": {"name": "Выдача/замена периферийных устройств"},
    "status": {"name": "Закрыто", "code": "closed", "status_type": "CLOSED", "next_alarm": None},
    "cache_status_type": "CLOSED",
    "scheme_wf": {"name": "SD схема БП", "code": "SWF-000008"},
    "epic": None,
    "tags": [],
    "assets": [],
    "components": [],
    "comments": [
        {
            "id": "CmfComment:1",
            "cmf_created_at": "2026-07-13T08:39:34.325446+03:00",
            "text": "Создано",
            "cache_cmf_author_name": "Слободенюк Валерий Валериевич",
            "log_level": 2,
            "private": False,
        }
    ],
    "timetracker_history": [
        {
            "id": "CmfTimeTrackerHistory:1",
            "code": "TTH-041857",
            "start_date": "2026-09-08T16:23:14.156000+03:00",
            "end_date": "2026-09-08T18:53:14.156000+03:00",
            "cmf_created_at": "2026-09-08T16:23:20.842186+03:00",
            "time_spent": 150,
            "history_type": "fact",
            "text": "",
            "cmf_owner": {"name": "Пчелин Василий Андреевич", "login": "v.pchelin@nord.local"},
        }
    ],
}


class FakeClient:
    token = "eva-token"

    def get_project(self, code):
        return SAMPLE_PROJECT

    def list_tasks(self, project_id, modified_from, modified_to=None):
        return [SAMPLE_TASK]


@override_settings(SYNC_TOKEN="secret-token", EVA_TOKEN="eva-token")
class SyncViewTests(TestCase):
    def test_unauthorized(self):
        url = reverse("er_tasks:sync")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 401)

    def test_sync_ok(self):
        url = reverse("er_tasks:sync")
        with patch("er_tasks.views.run_sync") as mocked:
            mocked.return_value = {
                "ok": True,
                "tasks_upserted": 1,
                "watermark": None,
                "duration_sec": 0.1,
                "error": "",
            }
            response = self.client.post(url, HTTP_X_SYNC_TOKEN="secret-token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_run_sync_upserts(self):
        SyncState.objects.create(
            project_code="NS",
            last_modified_watermark=timezone.now() - timedelta(days=1),
        )
        result = run_sync(client=FakeClient(), batch_days=30)
        self.assertEqual(result["tasks_upserted"], 1)
        task = Task.objects.get(code="NS-27278")
        self.assertEqual(task.status_type, "CLOSED")
        self.assertEqual(task.comments.count(), 1)
        self.assertEqual(task.time_entries.count(), 1)
        self.assertEqual(float(task.labor_hours), 2.5)


class DashboardTests(TestCase):
    def test_pages_render(self):
        now = timezone.now()
        Task.objects.create(
            eva_id="CmfTask:1",
            code="NS-1",
            url="https://eva.nordstar.ru/project/Task/NS-1",
            project_code="NS",
            name="Test",
            status="Открыто",
            status_type="OPEN",
            created_at=now,
            modified_at=now,
        )
        for name in ("volume", "aging", "queues", "custom"):
            response = self.client.get(reverse(f"er_tasks:{name}"))
            self.assertEqual(response.status_code, 200, name)
