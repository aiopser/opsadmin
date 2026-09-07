from django.urls import path

from .consumer import TaskLogWebsocket


websocket_urlpatterns = [
    path(
        "ws/ansible/tasks/log/", TaskLogWebsocket.as_asgi(), name="ansible-task-log-ws"
    ),
]
