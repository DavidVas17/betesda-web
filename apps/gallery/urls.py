from django.urls import path

from . import views

app_name = "gallery"
urlpatterns = [
    path("", views.album_list, name="list"),
    path("<slug:slug>/", views.detail, name="detail"),
]
