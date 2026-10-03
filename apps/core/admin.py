from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import SiteConfiguration


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    save_on_top = True
    readonly_fields = ("updated_at",)
    fieldsets = [
        ("Identidad", {"fields": ("institution_name", "slogan")}),
        ("Contacto", {"fields": ("phone", "email", "address")}),
        ("Enlaces", {"fields": ("facebook_url", "map_url")}),
        ("Registro", {"fields": ("updated_at",), "classes": ("collapse",)}),
    ]

    def changelist_view(self, request, extra_context=None):
        """Solo existe una configuracion: lleva directo a editarla (o a crearla)."""
        config = SiteConfiguration.objects.first()
        if config is not None and self.has_view_or_change_permission(request, config):
            return redirect(reverse("admin:core_siteconfiguration_change", args=[config.pk]))
        if config is None and self.has_add_permission(request):
            return redirect(reverse("admin:core_siteconfiguration_add"))
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request) -> bool:
        return not SiteConfiguration.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
