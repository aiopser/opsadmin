from rest_framework.routers import SimpleRouter

from .views import WikiPageViewSet

router = SimpleRouter(trailing_slash=False)
router.register(r"v1/wiki/pages", WikiPageViewSet, basename="wiki-pages")

urlpatterns = router.urls
