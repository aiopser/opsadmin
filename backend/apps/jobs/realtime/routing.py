from django.urls import path
from .consumer import RunEventsConsumer

websocket_urlpatterns = [path("ws/jobs/runs/", RunEventsConsumer.as_asgi())]
