from django.utils import timezone

from .models import Post


def published_posts():
    return Post.objects.filter(
        status=Post.Status.PUBLISHED, published_at__lte=timezone.now()
    ).order_by("-published_at", "-created_at", "-pk")
