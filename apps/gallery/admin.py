from django import forms
from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max
from django.http import Http404
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.backoffice.utils import badge, count_message, preview_html, thumbnail_html

from .forms import BulkPhotoUploadForm
from .models import Album, Photo


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ("preview", "image", "alt_text", "caption", "order")
    readonly_fields = ("preview",)

    @admin.display(description="Vista")
    def preview(self, obj):
        return thumbnail_html(obj.image, size=64) if obj.pk else "—"


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ("cover", "title", "event_date", "photo_total", "published_badge", "updated_at")
    list_display_links = ("title",)
    list_filter = ("is_published", "event_date")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (PhotoInline,)
    save_on_top = True
    list_per_page = 25
    actions = ("publish_albums", "unpublish_albums")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_photo_total=Count("photos"))
            .prefetch_related("photos")
        )

    @admin.display(description="Portada")
    def cover(self, obj):
        photos = list(obj.photos.all())
        return thumbnail_html(photos[0].image) if photos else thumbnail_html(None)

    @admin.display(description="Fotos", ordering="_photo_total")
    def photo_total(self, obj):
        return obj._photo_total

    @admin.display(description="Estado", ordering="is_published")
    def published_badge(self, obj):
        return badge("Publicado", "ok") if obj.is_published else badge("Borrador", "warn")

    @admin.action(description="Publicar álbumes seleccionados", permissions=["change"])
    def publish_albums(self, request, queryset) -> None:
        updated = queryset.update(is_published=True, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'álbum publicado', 'álbumes publicados')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Despublicar álbumes seleccionados", permissions=["change"])
    def unpublish_albums(self, request, queryset) -> None:
        updated = queryset.update(is_published=False, updated_at=timezone.now())
        self.message_user(
            request,
            f"{count_message(updated, 'álbum despublicado', 'álbumes despublicados')}.",
            messages.WARNING,
        )

    # --- Subida masiva de fotografias ------------------------------------------
    def get_urls(self):
        opts = self.model._meta
        custom = [
            path(
                "<path:object_id>/subir-fotos/",
                self.admin_site.admin_view(self.upload_photos_view),
                name=f"{opts.app_label}_{opts.model_name}_upload_photos",
            ),
        ]
        # Debe ir antes de las URLs por defecto, que incluyen un patron "<path:object_id>/".
        return custom + super().get_urls()

    def upload_photos_view(self, request, object_id):
        album = self.get_object(request, unquote(object_id))
        if album is None:
            raise Http404("El álbum no existe.")
        if not self.has_change_permission(request, album):
            raise PermissionDenied

        if request.method == "POST":
            form = BulkPhotoUploadForm(request.POST, request.FILES)
            if form.is_valid():
                created = self._create_photos(album, form)
                self.message_user(
                    request,
                    f"Se agregaron {count_message(created, 'fotografía', 'fotografías')} "
                    f"a «{album.title}». Revisa el texto alternativo de cada una.",
                    messages.SUCCESS,
                )
                return redirect(reverse("admin:gallery_album_change", args=[album.pk]))
        else:
            form = BulkPhotoUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": album,
            "title": "Subir varias fotografías",
            "subtitle": album.title,
            "form": form,
            "media": self.media + form.media,
            "has_view_permission": self.has_view_permission(request, album),
        }
        return TemplateResponse(request, "admin/gallery/album/upload_photos.html", context)

    @staticmethod
    def _create_photos(album, form: forms.Form) -> int:
        files = form.cleaned_data["images"]
        alt_text = form.cleaned_data["alt_text"].strip() or f"Fotografía de {album.title}"[:180]
        last_order = album.photos.aggregate(top=Max("order"))["top"]
        next_order = 0 if last_order is None else last_order + 1
        with transaction.atomic():
            for offset, image in enumerate(files):
                Photo.objects.create(
                    album=album,
                    image=image,
                    alt_text=alt_text,
                    order=next_order + offset,
                )
        return len(files)


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "alt_text", "album", "order", "created_at")
    list_display_links = ("alt_text",)
    list_editable = ("order",)
    list_filter = ("album",)
    list_select_related = ("album",)
    search_fields = ("alt_text", "caption", "album__title")
    readonly_fields = ("image_preview",)
    list_per_page = 40
    fields = ("album", "image", "image_preview", "alt_text", "caption", "order")

    @admin.display(description="Foto")
    def thumbnail(self, obj):
        return thumbnail_html(obj.image, size=56)

    @admin.display(description="Vista previa")
    def image_preview(self, obj):
        return preview_html(obj.image)
