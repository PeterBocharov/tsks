import os
from uuid import uuid4

import requests
from django.conf import settings


TASK_FIELDS = [
    "cmf_author.name",
    "cmf_author.login",
    "cmf_owner.name",
    "request_type.name",
    "responsible.name",
    "responsible.login",
    "cmf_created_at",
    "cmf_modified_at",
    "status_closed_at",
    "timetracker_history.*",
    "timetracker_history.cmf_owner.name",
    "timetracker_history.cmf_owner.login",
    "parent.name",
    "epic.*",
    "cmf_modified_by",
    "epic.cmf_owner.name",
    "status",
    "status.name",
    "status.code",
    "status.status_type",
    "status.next_alarm",
    "cache_status_type",
    "text",
    "components.*",
    "components.cmf_owner.name",
    "tags",
    "assets",
    "comments.*",
    "scheme_wf",
]


class EvaClient:
    def __init__(self, url=None, token=None):
        self.url = (url or settings.EVA_URL)
        self.token = token or settings.EVA_TOKEN
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"


    def call(self, method, params=None, args=None, fields="*", filter=None, flags=None):
        if flags is None:
            flags = {"admin_mode": True}
        payload = {
            "callid": str(uuid4()),
            "method": method,
            "args": args,
            "kwargs": params,
            "fields": fields,
            "filter": filter,
            "flags": flags,
            "jsonrpc": "2.2",
        }
        if not fields:
            payload.pop("fields")
        if not params:
            payload.pop("kwargs")
        if not filter:
            payload.pop("filter")
        if not args:
            payload.pop("args")
        resp = self.session.post(os.path.join(self.url, "api/"), json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data

    def get_project(self, code):
        data = self.call(
            "CmfProject.get",
            params={"filter": ["code", "==", code]},
            fields=["id", "name", "code"],
        )
        return data["result"]

    def list_tasks(self, project_id, modified_from, modified_to=None):
        date_filter = [
            ["parent_id", "==", project_id],
            ["system", "==", False],
            ["cmf_modified_at", ">=", modified_from],
        ]
        if modified_to:
            date_filter.append(["cmf_modified_at", "<=", modified_to])
        data = self.call(
            "CmfTask.list",
            params={
                "filter": date_filter,
                "fields": TASK_FIELDS,
                "include_archived": "true",
            },
        )
        return data.get("result") or []
