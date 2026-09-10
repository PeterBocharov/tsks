from django.urls import path

from . import views

app_name = "er_tasks"

urlpatterns = [
    path("api/sync/", views.sync_view, name="sync"),
    path("", views.volume, name="volume"),
    path("aging/", views.aging, name="aging"),
    path("queues/", views.queues, name="queues"),
    path("custom/", views.custom, name="custom"),
]
