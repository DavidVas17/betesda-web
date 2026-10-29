from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.events.models import Event
from apps.gallery.models import Album
from apps.news.selectors import published_posts


class PagesSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        return [
            ("core:home", 1.0),
            ("core:about", 0.8),
            ("core:ministries", 0.7),
            ("events:list", 0.8),
            ("news:list", 0.7),
            ("gallery:list", 0.6),
            ("contacts:contact", 0.7),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class EventsSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Event.objects.filter(is_published=True).order_by("-starts_at")

    def lastmod(self, item):
        return item.updated_at


class NewsSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return published_posts()

    def lastmod(self, item):
        return item.updated_at


class GallerySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.4

    def items(self):
        return Album.objects.filter(is_published=True).order_by("-pk")

    def location(self, item):
        return reverse("gallery:detail", args=[item.slug])

    def lastmod(self, item):
        return item.updated_at


SITEMAPS = {
    "paginas": PagesSitemap,
    "eventos": EventsSitemap,
    "noticias": NewsSitemap,
    "galeria": GallerySitemap,
}
