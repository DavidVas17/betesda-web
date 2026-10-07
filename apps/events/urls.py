from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.event_list, name="list"),
    path("<slug:slug>/", views.detail, name="detail"),
]
