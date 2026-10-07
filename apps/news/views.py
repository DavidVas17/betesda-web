from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .selectors import published_posts


def post_list(request):
    page = Paginator(published_posts(), 9).get_page(request.GET.get("pagina"))
    return render(request, "news/list.html", {"page_obj": page})


def detail(request, slug):
    post = get_object_or_404(published_posts(), slug=slug)
    return render(request, "news/detail.html", {"post": post})
