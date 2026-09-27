"""
App configuration for the reports Django app.

Initializes the Firebase Admin SDK on app startup so push notification
features are ready before any request or signal handler needs them.
"""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reports'

    def ready(self):
        from reports.firebase_init import initialize_firebase
        initialize_firebase()
