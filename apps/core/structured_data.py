"""Datos estructurados (schema.org) para que Google muestre la iglesia y sus eventos."""

from django.utils import timezone


def church(site: dict, request, service_times=()) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "Church",
        "name": site.get("name"),
        "url": request.build_absolute_uri("/"),
        "logo": request.build_absolute_uri("/static/images/logo-betesda.png"),
        "image": request.build_absolute_uri("/static/images/og-betesda.jpg"),
        "slogan": site.get("slogan") or None,
        "telephone": site.get("phone_link") or None,
        "email": site.get("email") or None,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": site.get("address"),
            "addressLocality": "Villa Nueva",
            "addressRegion": "Guatemala",
            "addressCountry": "GT",
        },
        "sameAs": [url for url in (site.get("facebook_url"),) if url],
    }
    days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    hours = [
        {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": f"https://schema.org/{days[item.day]}",
            "opens": item.starts_at.strftime("%H:%M"),
            **({"closes": item.ends_at.strftime("%H:%M")} if item.ends_at else {}),
            "description": item.name,
        }
        for item in service_times
    ]
    if hours:
        data["openingHoursSpecification"] = hours
    return {key: value for key, value in data.items() if value}


def event(item, site: dict, request) -> dict:
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": item.title,
        "description": item.summary,
        "startDate": timezone.localtime(item.starts_at).isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": request.build_absolute_uri(item.get_absolute_url()),
        "location": {
            "@type": "Place",
            "name": item.location,
            "address": site.get("address"),
        },
        "organizer": {
            "@type": "Organization",
            "name": site.get("name"),
            "url": request.build_absolute_uri("/"),
        },
        "isAccessibleForFree": True,
    }
    if item.ends_at:
        data["endDate"] = timezone.localtime(item.ends_at).isoformat()
    if item.large_image_url:
        data["image"] = [request.build_absolute_uri(item.large_image_url)]
    return data
