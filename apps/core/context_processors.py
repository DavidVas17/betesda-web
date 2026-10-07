from urllib.parse import urlencode

from django.db import DatabaseError
from django.urls import reverse

from .content import INSTITUTION
from .models import SiteConfiguration


def public_site(request):
    site = INSTITUTION.copy()
    try:
        configuration = SiteConfiguration.objects.first()
    except DatabaseError:
        configuration = None
    if configuration:
        for source, destination in (
            ("institution_name", "name"),
            ("slogan", "slogan"),
            ("phone", "phone"),
            ("email", "email"),
            ("address", "address"),
            ("facebook_url", "facebook_url"),
        ):
            if value := getattr(configuration, source):
                site[destination] = value
    digits = "".join(character for character in site["phone"] if character.isdigit())
    site["phone_link"] = f"+502{digits}" if len(digits) == 8 else f"+{digits}"
    default_map_url = (
        "https://www.google.com/maps/search/?" + urlencode({"api": 1, "query": site["address"]})
        if site["address"] != INSTITUTION["address"]
        else INSTITUTION["map_url"]
    )
    site["map_url"] = (
        configuration.map_url if configuration and configuration.map_url else default_map_url
    )
    location = (
        {"cid": INSTITUTION["map_cid"]}
        if site["map_url"] == INSTITUTION["map_url"]
        else {"q": f"{site['address']} Guatemala"}
    )
    site["map_embed_url"] = "https://www.google.com/maps?" + urlencode(
        {**location, "output": "embed", "z": 18, "hl": "es"}
    )
    match = request.resolver_match
    navigation = []
    for label, route in (
        ("Inicio", "core:home"),
        ("Nosotros", "core:about"),
        ("Ministerios", "core:ministries"),
        ("Eventos", "events:list"),
        ("Noticias", "news:list"),
        ("Galería", "gallery:list"),
        ("Contacto", "contacts:contact"),
    ):
        namespace, name = route.split(":")
        active = bool(match and match.namespace == namespace)
        if namespace == "core":
            active = active and match.url_name == name
        navigation.append({"label": label, "url": reverse(route), "active": active})
    return {"site": site, "navigation": navigation}
