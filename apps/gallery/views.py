from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from .models import Album


def album_list(request):
    albums = (
        Album.objects.filter(is_published=True)
        .annotate(photo_count=Count("photos"))
        .order_by("-event_date", "-created_at", "-pk")
    )
    page = Paginator(albums.prefetch_related("photos"), 9).get_page(request.GET.get("pagina"))
    return render(request, "gallery/list.html", {"page_obj": page})


def detail(request, slug):
    album = get_object_or_404(Album, slug=slug, is_published=True)
    page = Paginator(album.photos.all(), 24).get_page(request.GET.get("pagina"))
    return render(request, "gallery/detail.html", {"album": album, "page_obj": page})
