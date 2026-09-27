"""
Channels WebSocket URL routing for the reports app.

Maps the ws/notifications/ path to NotificationConsumer; included by
config/asgi.py's ProtocolTypeRouter.
"""

from django.urls import path

from reports import consumers

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]
