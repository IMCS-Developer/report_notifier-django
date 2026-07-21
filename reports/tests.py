from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from config.asgi import application


class ReportsFeedConsumerTests(TransactionTestCase):
    """
    Verifies NotificationConsumer (reports/consumers.py) actually forwards
    "reports_feed" group broadcasts to a connected client, using the same
    type/payload shape reports/social_views.py's group_send() calls produce.
    """

    async def test_report_comment_update_is_forwarded(self):
        communicator = WebsocketCommunicator(application, "/ws/notifications/?nik=TEST123")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        connection_status = await communicator.receive_json_from()
        self.assertEqual(connection_status["type"], "connection_status")

        channel_layer = get_channel_layer()
        payload = {
            "encoded_key": "20260720_Test_Shift",
            "comments_count": 1,
            "new_comment": {
                "id": 999999,
                "report_id": "20260720_Test_Shift",
                "user": "Test User",
                "user_nik": "TEST123",
                "message": "test comment from verification",
            },
        }
        await channel_layer.group_send(
            "reports_feed",
            {"type": "report_comment_update", "message": payload},
        )

        response = await communicator.receive_json_from(timeout=2)
        self.assertEqual(response["type"], "report_comment_update")
        self.assertEqual(response["message"]["encoded_key"], "20260720_Test_Shift")
        self.assertEqual(
            response["message"]["new_comment"]["message"],
            "test comment from verification",
        )

        await communicator.disconnect()
