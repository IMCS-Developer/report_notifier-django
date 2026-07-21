import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = 'reports_feed'

    async def connect(self):
        query_params = parse_qs(self.scope['query_string'].decode())
        self.nik = query_params.get('nik', [''])[0]
        self.report_id = query_params.get('report_id', [''])[0]

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connection_status',
            'payload': {'message': 'Connected to notification channel', 'status': 'connected'}
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        pass

    async def report_comment_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'report_comment_update',
            'message': event['message'],
        }))

    async def report_reaction_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'report_reaction_update',
            'message': event['message'],
        }))

    async def comment_reaction_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'comment_reaction_update',
            'comment_data': event['message'],
        }))

    async def report_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'report_update',
            'message': event['message'],
        }))
