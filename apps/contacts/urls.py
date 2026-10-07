from django.urls import path

from . import views

app_name = "contacts"

urlpatterns = [
    path("", views.contact, name="contact"),
    path("enviar/", views.send_message, name="send"),
]
