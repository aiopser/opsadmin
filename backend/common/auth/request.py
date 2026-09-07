from django.conf import settings

from apps.user.models import UserProfile


def get_user(request):
    if settings.DEBUG:
        try:
            return request.user
        except Exception:
            return None
    try:
        return UserProfile.objects.filter(id=request.user.id).first()
    except Exception as exc:
        raise Exception("Unable to get authenticated user") from exc


def get_user_name(request):
    if request.user:
        return request.user.name
    if settings.DEBUG:
        return "agent"
    raise Exception("Unable to get authenticated user")


def get_addr(request):
    if "HTTP_X_FORWARDED_FOR" in request.META:
        return request.META["HTTP_X_FORWARDED_FOR"]
    return request.META["REMOTE_ADDR"]
