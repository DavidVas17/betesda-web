from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("nosotros/", views.about, name="about"),
    path("ministerios/", views.ministries, name="ministries"),
    path("favicon.ico", views.favicon, name="favicon"),
    path("health/live/", views.live, name="health-live"),
    path("health/ready/", views.ready, name="health-ready"),
]
