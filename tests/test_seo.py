"""Buscadores y vista previa al compartir."""

import json
import re
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event
from apps.news.models import Post

pytestmark = pytest.mark.django_db


def meta(content, prop):
    match = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', content)
    return match.group(1) if match else None


def ld(content):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', content, re.S)
    return [json.loads(block) for block in blocks]


def event(**extra):
    values = {
        "title": "Vigilia de oración",
        "summary": "Una noche para orar juntos",
        "description": "Detalles",
        "starts_at": timezone.now() + timedelta(days=3),
        "location": "Templo principal",
        "is_published": True,
    }
    values.update(extra)
    return Event.objects.create(**values)


def test_home_has_share_preview_and_church_data(client):
    content = client.get("/").content.decode()

    assert meta(content, "og:image") == "http://testserver/static/images/og-betesda.jpg"
    assert meta(content, "og:url") == "http://testserver/"
    assert meta(content, "twitter:card") == "summary_large_image"
    assert '<link rel="canonical" href="http://testserver/">' in content
    church = ld(content)[0]
    assert church["@type"] == "Church"
    assert church["address"]["addressCountry"] == "GT"


def test_event_page_shares_its_own_title_and_event_data(client):
    item = event()

    content = client.get(item.get_absolute_url()).content.decode()

    assert meta(content, "og:title") == "Vigilia de oración"
    assert "Una noche para orar juntos" in meta(content, "og:description")
    data = ld(content)[0]
    assert data["@type"] == "Event" and data["name"] == "Vigilia de oración"
    assert data["location"]["name"] == "Templo principal"


def test_json_ld_cannot_break_out_of_the_script(client):
    item = event(title="</script><script>alert(1)</script>")

    content = client.get(item.get_absolute_url()).content.decode()

    assert "<script>alert(1)</script>" not in content
    assert ld(content)[0]["name"] == "</script><script>alert(1)</script>"


def test_news_is_shared_as_article(client, django_user_model):
    author = django_user_model.objects.create_user("autor")
    post = Post.objects.create(
        title="Nuevo horario",
        excerpt="Cambia la escuela dominical",
        body="Texto",
        status=Post.Status.PUBLISHED,
        author=author,
    )

    content = client.get(post.get_absolute_url()).content.decode()

    assert meta(content, "og:type") == "article"
    assert meta(content, "og:title") == "Nuevo horario"


def test_sitemap_lists_public_pages_only(client):
    public = event(title="Público")
    hidden = event(title="Borrador", is_published=False)

    content = client.get("/sitemap.xml").content.decode()

    assert "http://testserver/nosotros/" in content
    assert public.get_absolute_url() in content
    assert hidden.get_absolute_url() not in content
    assert "/panel/" not in content


def test_robots_points_to_the_sitemap(client):
    assert "Sitemap: http://testserver/sitemap.xml" in client.get("/robots.txt").content.decode()
