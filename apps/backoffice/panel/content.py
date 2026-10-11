from django.contrib import messages
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.events.models import Event
from apps.gallery.forms import BulkPhotoUploadForm
from apps.gallery.models import Album, Photo
from apps.news.models import Post

from .access import panel_required
from .content_forms import AlbumForm, EventForm, PhotoForm, PostForm
from .utils import audit, paginate, pagination_query, panel_render

PUBLICATION_CHOICES = (
    ("all", "Todos"),
    ("published", "Publicados"),
    ("draft", "Borradores"),
)
NEWS_CHOICES = (("all", "Todas"), *Post.Status.choices)


def _require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


def _preview(obj):
    if isinstance(obj, Post):
        visible = (
            obj.status == Post.Status.PUBLISHED
            and obj.published_at
            and obj.published_at <= timezone.now()
        )
    else:
        visible = obj.is_published
    if not visible:
        return ""
    if isinstance(obj, Album):
        return reverse("gallery:detail", args=[obj.slug])
    return obj.get_absolute_url()


def _list(request, *, model, section, singular, title, search_fields):
    queryset = model.objects.all()
    is_news = model is Post
    status_choices = NEWS_CHOICES if is_news else PUBLICATION_CHOICES
    status = request.GET.get("status", "all")
    if status not in {value for value, _ in status_choices}:
        status = "all"
    query = request.GET.get("q", "").strip()[:200]
    published = Q(status=Post.Status.PUBLISHED) if is_news else Q(is_published=True)
    draft = Q(status=Post.Status.DRAFT) if is_news else Q(is_published=False)
    counts = queryset.aggregate(
        total=Count("pk"),
        published=Count("pk", filter=published),
        draft=Count("pk", filter=draft),
    )
    if is_news:
        counts["archived"] = queryset.filter(status=Post.Status.ARCHIVED).count()
        queryset = queryset.select_related("author").order_by("-created_at", "-pk")
        if status != "all":
            queryset = queryset.filter(status=status)
    else:
        if status == "published":
            queryset = queryset.filter(is_published=True)
        elif status == "draft":
            queryset = queryset.filter(is_published=False)
        if model is Event:
            queryset = queryset.order_by("-starts_at", "-pk")
        else:
            queryset = queryset.annotate(photo_count=Count("photos")).order_by(
                "-event_date", "-created_at", "-pk"
            )
    if query:
        search = Q()
        for field in search_fields:
            search |= Q(**{f"{field}__icontains": query})
        queryset = queryset.filter(search)
    app = model._meta.app_label
    can_change = request.user.has_perm(f"{app}.change_{model._meta.model_name}")
    can_delete = request.user.has_perm(f"{app}.delete_{model._meta.model_name}")
    can_add = request.user.has_perm(f"{app}.add_{model._meta.model_name}")
    page_obj = paginate(request, queryset)
    for obj in page_obj:
        obj.edit_url = reverse(f"panel:{singular}_edit", args=[obj.pk])
        obj.action_url = reverse(f"panel:{singular}_action", args=[obj.pk])
        allow_delete = can_delete
        if model is Album and obj.photo_count:
            allow_delete = allow_delete and request.user.has_perm("gallery.delete_photo")
        obj.delete_url = reverse(f"panel:{singular}_delete", args=[obj.pk]) if allow_delete else ""
        obj.preview_url = _preview(obj)
        if is_news:
            obj.status_label = obj.get_status_display()
            obj.status_tone = {
                Post.Status.PUBLISHED: "success",
                Post.Status.DRAFT: "warning",
                Post.Status.ARCHIVED: "neutral",
            }[obj.status]
            if (
                obj.status == Post.Status.PUBLISHED
                and obj.published_at
                and obj.published_at > timezone.now()
            ):
                obj.status_label = "Programada"
                obj.status_tone = "info"
        else:
            obj.status_label = "Publicado" if obj.is_published else "Borrador"
            obj.status_tone = "success" if obj.is_published else "warning"
    return panel_render(
        request,
        "panel/content_list.html",
        {
            "section": section,
            "page_obj": page_obj,
            "q": query,
            "query": query,
            "status": status,
            "status_choices": status_choices,
            "counts": counts,
            "can_change": can_change,
            "can_delete": can_delete,
            "can_duplicate": can_change and can_add,
            "create_url": reverse(f"panel:{singular}_create") if can_add else "",
            "pagination_query": pagination_query(request),
        },
        active=section,
        title=title,
        subtitle="Organiza el contenido que comparte nuestra comunidad.",
    )


@panel_required("events.view_event")
def event_list(request):
    return _list(
        request,
        model=Event,
        section="events",
        singular="event",
        title="Eventos",
        search_fields=("title", "summary", "description", "location"),
    )


@panel_required("news.view_post")
def news_list(request):
    return _list(
        request,
        model=Post,
        section="news",
        singular="news",
        title="Noticias",
        search_fields=("title", "excerpt", "body"),
    )


@panel_required("gallery.view_album")
def album_list(request):
    return _list(
        request,
        model=Album,
        section="gallery",
        singular="album",
        title="Galería",
        search_fields=("title", "description"),
    )


def _content_form(request, *, model, form_class, singular, section, label, pk=None):
    obj = get_object_or_404(model, pk=pk) if pk is not None else None
    creating = obj is None
    permission = (
        f"{model._meta.app_label}.{'add' if creating else 'change'}_{model._meta.model_name}"
    )
    can_save = request.user.has_perm(permission)
    form_title = (
        f"{'Crear' if creating else 'Editar'} {label.lower()}"
        if can_save
        else f"Detalles de {label.lower()}"
    )
    if request.method == "POST":
        _require_permission(request, permission)
        form = form_class(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            with transaction.atomic():
                saved = form.save(commit=False)
                if creating and model is Post:
                    saved.author = request.user
                saved.save()
                form.save_m2m()
                audit(
                    request,
                    saved,
                    flag=ADDITION if creating else CHANGE,
                    message="Contenido creado." if creating else "Contenido actualizado.",
                )
            messages.success(request, f"Se guardó {label.lower()} correctamente.")
            return redirect(f"panel:{singular}_edit", pk=saved.pk)
    else:
        form = form_class(instance=obj, readonly=not can_save)
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": form_title,
            "form_intro": "Completa la información y elige cuándo compartirla en el sitio web.",
            "cancel_url": reverse(f"panel:{singular}_list"),
            "submit_label": "Guardar cambios",
            "object": obj,
            "preview_url": _preview(obj) if obj else "",
            "can_save": can_save,
            "delete_url": (
                reverse(f"panel:{singular}_delete", args=[obj.pk])
                if obj
                and request.user.has_perm(
                    f"{model._meta.app_label}.delete_{model._meta.model_name}"
                )
                else ""
            ),
        },
        active=section,
        title=form_title,
        subtitle="Los cambios se guardan en el contenido de la iglesia.",
    )


@panel_required("events.add_event")
@require_http_methods(["GET", "POST"])
def event_create(request):
    return _content_form(
        request,
        model=Event,
        form_class=EventForm,
        singular="event",
        section="events",
        label="Evento",
    )


@panel_required(("events.view_event", "events.change_event"))
@require_http_methods(["GET", "POST"])
def event_edit(request, pk):
    return _content_form(
        request,
        model=Event,
        form_class=EventForm,
        singular="event",
        section="events",
        label="Evento",
        pk=pk,
    )


@panel_required("news.add_post")
@require_http_methods(["GET", "POST"])
def news_create(request):
    return _content_form(
        request,
        model=Post,
        form_class=PostForm,
        singular="news",
        section="news",
        label="Noticia",
    )


@panel_required(("news.view_post", "news.change_post"))
@require_http_methods(["GET", "POST"])
def news_edit(request, pk):
    return _content_form(
        request,
        model=Post,
        form_class=PostForm,
        singular="news",
        section="news",
        label="Noticia",
        pk=pk,
    )


@panel_required("gallery.add_album")
@require_http_methods(["GET", "POST"])
def album_create(request):
    return _content_form(
        request,
        model=Album,
        form_class=AlbumForm,
        singular="album",
        section="gallery",
        label="Álbum",
    )


def _album_context(request, album, *, form=None, upload_form=None):
    can_edit = request.user.has_perm("gallery.change_album")
    can_add = (
        request.user.has_perm("gallery.add_photo")
        and request.user.has_perm("gallery.view_album")
        and can_edit
    )
    can_change_photo = request.user.has_perm("gallery.change_photo")
    can_view_photo = request.user.has_perm("gallery.view_photo") or can_change_photo
    can_delete_photo = request.user.has_perm("gallery.delete_photo")
    photos = list(album.photos.order_by("order", "created_at", "pk"))
    for photo in photos:
        photo.edit_url = (
            reverse("panel:photo_edit", args=[album.pk, photo.pk]) if can_view_photo else ""
        )
        photo.delete_url = (
            reverse("panel:photo_delete", args=[album.pk, photo.pk]) if can_delete_photo else ""
        )
    allow_delete = request.user.has_perm("gallery.delete_album") and (
        not photos or can_delete_photo
    )
    return {
        "album": album,
        "object": album,
        "photos": photos,
        "form": form if form is not None else AlbumForm(instance=album, readonly=not can_edit),
        "upload_form": upload_form if upload_form is not None else BulkPhotoUploadForm(),
        "can_edit_album": can_edit,
        "can_save": can_edit,
        "can_add_photo": can_add,
        "can_change_photo": can_change_photo,
        "can_delete_photo": can_delete_photo,
        "preview_url": _preview(album),
        "upload_url": reverse("panel:album_upload", args=[album.pk]),
        "delete_url": reverse("panel:album_delete", args=[album.pk]) if allow_delete else "",
        "cancel_url": reverse("panel:album_list"),
        "submit_label": "Guardar álbum",
        "form_title": "Información del álbum",
    }


@panel_required(("gallery.view_album", "gallery.change_album"))
@require_http_methods(["GET", "POST"])
def album_edit(request, pk):
    album = get_object_or_404(Album, pk=pk)
    form = None
    if request.method == "POST":
        _require_permission(request, "gallery.change_album")
        form = AlbumForm(request.POST, instance=album)
        if form.is_valid():
            with transaction.atomic():
                album = form.save()
                audit(request, album, message="Información del álbum actualizada.")
            messages.success(request, "Álbum actualizado correctamente.")
            return redirect("panel:album_edit", pk=album.pk)
    return panel_render(
        request,
        "panel/album_detail.html",
        _album_context(request, album, form=form),
        active="gallery",
        title=album.title,
        subtitle="Organiza el álbum y sus fotografías.",
    )


def _delete(request, *, obj, singular, section, label, cancel_url, message):
    if request.method == "POST":
        with transaction.atomic():
            audit(request, obj, flag=DELETION, message="Contenido eliminado.")
            obj.delete()
        messages.success(request, f"Se eliminó {label.lower()} correctamente.")
        return redirect(cancel_url)
    return panel_render(
        request,
        "panel/delete.html",
        {
            "object": obj,
            "object_label": label,
            "cancel_url": cancel_url,
            "delete_message": message,
        },
        active=section,
        title=f"Eliminar {label.lower()}",
        subtitle="Revisa la información antes de confirmar.",
    )


@panel_required("events.delete_event")
@require_http_methods(["GET", "POST"])
def event_delete(request, pk):
    return _delete(
        request,
        obj=get_object_or_404(Event, pk=pk),
        singular="event",
        section="events",
        label="Evento",
        cancel_url=reverse("panel:event_list"),
        message="El evento dejará de aparecer en el sitio web. Esta acción no se puede deshacer.",
    )


@panel_required("news.delete_post")
@require_http_methods(["GET", "POST"])
def news_delete(request, pk):
    return _delete(
        request,
        obj=get_object_or_404(Post, pk=pk),
        singular="news",
        section="news",
        label="Noticia",
        cancel_url=reverse("panel:news_list"),
        message="La noticia dejará de aparecer en el sitio web. Esta acción no se puede deshacer.",
    )


@panel_required("gallery.delete_album")
@require_http_methods(["GET", "POST"])
def album_delete(request, pk):
    with transaction.atomic():
        albums = Album.objects.select_for_update() if request.method == "POST" else Album.objects
        album = get_object_or_404(albums, pk=pk)
        if album.photos.exists():
            _require_permission(request, "gallery.delete_photo")
        return _delete(
            request,
            obj=album,
            singular="album",
            section="gallery",
            label="Álbum",
            cancel_url=reverse("panel:album_list"),
            message=(
                "Se eliminarán el álbum y todas sus fotografías de la galería. "
                "Esta acción no se puede deshacer."
            ),
        )


@panel_required("events.change_event")
@require_POST
def event_action(request, pk):
    action = request.POST.get("action", "")
    if action not in {"publish", "unpublish", "feature", "unfeature", "duplicate"}:
        return HttpResponseBadRequest("La acción no es válida.")
    if action == "duplicate":
        _require_permission(request, "events.add_event")
    with transaction.atomic():
        event = get_object_or_404(Event.objects.select_for_update(), pk=pk)
        if action == "duplicate":
            event = Event.objects.create(
                title=f"{event.title[:171]} (copia)",
                summary=event.summary,
                description=event.description,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                location=event.location,
                cover_image=event.cover_image,
                is_published=False,
                is_featured=False,
            )
            audit(request, event, flag=ADDITION, message="Evento duplicado como borrador.")
        else:
            field = "is_published" if action in {"publish", "unpublish"} else "is_featured"
            setattr(event, field, action in {"publish", "feature"})
            event.save(update_fields=[field, "updated_at"])
            audit(request, event, message="Estado del evento actualizado.")
    messages.success(
        request,
        "Copia creada como borrador. Ajusta la fecha antes de publicar."
        if action == "duplicate"
        else "Estado del evento actualizado.",
    )
    return (
        redirect("panel:event_edit", pk=event.pk)
        if action == "duplicate"
        else redirect("panel:event_list")
    )


@panel_required("news.change_post")
@require_POST
def news_action(request, pk):
    action = request.POST.get("action", "")
    if action not in {"publish", "draft", "archive", "feature", "unfeature"}:
        return HttpResponseBadRequest("La acción no es válida.")
    with transaction.atomic():
        post = get_object_or_404(Post.objects.select_for_update(), pk=pk)
        if action in {"feature", "unfeature"}:
            post.is_featured = action == "feature"
        else:
            post.status = {
                "publish": Post.Status.PUBLISHED,
                "draft": Post.Status.DRAFT,
                "archive": Post.Status.ARCHIVED,
            }[action]
        post.save()
        audit(request, post, message="Estado de la noticia actualizado.")
    messages.success(request, "Estado de la noticia actualizado.")
    return redirect("panel:news_list")


@panel_required("gallery.change_album")
@require_POST
def album_action(request, pk):
    action = request.POST.get("action", "")
    if action not in {"publish", "unpublish"}:
        return HttpResponseBadRequest("La acción no es válida.")
    with transaction.atomic():
        album = get_object_or_404(Album.objects.select_for_update(), pk=pk)
        album.is_published = action == "publish"
        album.save(update_fields=["is_published", "updated_at"])
        audit(request, album, message="Estado del álbum actualizado.")
    messages.success(request, "Estado del álbum actualizado.")
    return redirect("panel:album_list")


@panel_required("gallery.add_photo")
@require_POST
def album_upload(request, pk):
    _require_permission(request, "gallery.view_album")
    _require_permission(request, "gallery.change_album")
    album = get_object_or_404(Album, pk=pk)
    form = BulkPhotoUploadForm(request.POST, request.FILES)
    if form.is_valid():
        files = form.cleaned_data["images"]
        with transaction.atomic():
            # Serialize uploads to an album before choosing the appended ordering.
            album = get_object_or_404(Album.objects.select_for_update(), pk=pk)
            last_order = album.photos.aggregate(top=Max("order"))["top"]
            next_order = 0 if last_order is None else last_order + 1
            if next_order + len(files) - 1 > 32767:
                form.add_error(None, "Este álbum alcanzó el límite de orden de fotografías.")
            else:
                alt_text = (
                    form.cleaned_data["alt_text"].strip() or f"Fotografía de {album.title}"[:180]
                )
                for offset, image in enumerate(files):
                    photo = Photo.objects.create(
                        album=album,
                        image=image,
                        alt_text=alt_text,
                        order=next_order + offset,
                    )
                    audit(request, photo, flag=ADDITION, message="Fotografía agregada al álbum.")
        if not form.errors:
            messages.success(request, f"Se agregaron {len(files)} fotografías al álbum.")
            return redirect("panel:album_edit", pk=album.pk)
    return panel_render(
        request,
        "panel/album_detail.html",
        _album_context(request, album, upload_form=form),
        active="gallery",
        title=album.title,
        subtitle="Revisa las imágenes e inténtalo de nuevo.",
    )


@panel_required(("gallery.view_photo", "gallery.change_photo"))
@require_http_methods(["GET", "POST"])
def photo_edit(request, album_pk, pk):
    _require_permission(request, "gallery.view_album")
    photo = get_object_or_404(Photo.objects.select_related("album"), pk=pk, album_id=album_pk)
    can_save = request.user.has_perm("gallery.change_photo")
    if request.method == "POST":
        _require_permission(request, "gallery.change_photo")
        form = PhotoForm(request.POST, request.FILES, instance=photo)
        if form.is_valid():
            with transaction.atomic():
                photo = form.save()
                audit(request, photo, message="Información de fotografía actualizada.")
            messages.success(request, "Fotografía actualizada correctamente.")
            return redirect("panel:album_edit", pk=photo.album_id)
    else:
        form = PhotoForm(instance=photo, readonly=not can_save)
    return panel_render(
        request,
        "panel/form.html",
        {
            "form": form,
            "form_title": "Editar fotografía" if can_save else "Detalles de fotografía",
            "form_intro": "Describe la imagen y elige su lugar en el álbum.",
            "cancel_url": reverse("panel:album_edit", args=[album_pk]),
            "submit_label": "Guardar fotografía",
            "object": photo,
            "can_save": can_save,
            "preview_url": _preview(photo.album),
            "delete_url": (
                reverse("panel:photo_delete", args=[album_pk, pk])
                if request.user.has_perm("gallery.delete_photo")
                else ""
            ),
        },
        active="gallery",
        title="Editar fotografía" if can_save else "Detalles de fotografía",
        subtitle=photo.album.title,
    )


@panel_required("gallery.delete_photo")
@require_http_methods(["GET", "POST"])
def photo_delete(request, album_pk, pk):
    _require_permission(request, "gallery.view_album")
    photo = get_object_or_404(Photo, pk=pk, album_id=album_pk)
    return _delete(
        request,
        obj=photo,
        singular="photo",
        section="gallery",
        label="Fotografía",
        cancel_url=reverse("panel:album_edit", args=[album_pk]),
        message="La fotografía dejará de aparecer en el álbum. Esta acción no se puede deshacer.",
    )
