"""Private-chat-only Telegram interface. Authorization precedes routing and storage."""
import logging
import re
import time

from notifications.notifier import Notifier, NullNotifier
from utils.http_client import HttpClient, FetchError


class TelegramAPI:
    def __init__(self, token, client=None):
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
            raise ValueError('TELEGRAM_BOT_TOKEN inválido ou ausente')
        self._token, self.client = token, client or HttpClient(timeout=40)

    def call(self, method, payload):
        data = self.client.json('https://api.telegram.org/bot' + self._token + '/' + method, payload)
        if not data.get('ok'):
            raise FetchError('Telegram recusou a operação')
        return data.get('result')

    def send(self, chat, message):
        # 1800 code points stay below 4096 UTF-16 units even for emoji.
        for start in range(0, len(message), 1800):
            self.call('sendMessage', {'chat_id': chat, 'text': message[start:start + 1800]})


class TelegramNotifier(Notifier):
    channel = 'telegram'

    def __init__(self, api, user_id):
        self.api, self.user_id = api, user_id

    def send(self, message):
        self.api.send(self.user_id, message)


class TelegramBot:
    def __init__(self, api, allowed_ids, agent_factory):
        if not allowed_ids or any(type(x) is not int or x <= 0 for x in allowed_ids):
            raise ValueError('Configure TELEGRAM_ALLOWED_USER_IDS com IDs numéricos positivos')
        self.api, self.allowed, self.factory = api, set(allowed_ids), agent_factory
        self.agents, self.last = {}, {}

    def process(self, update):
        message = update.get('message') or {}
        user = message.get('from') or {}
        chat = message.get('chat') or {}
        uid = user.get('id')
        if (uid not in self.allowed or user.get('is_bot') or chat.get('type') != 'private'
                or chat.get('id') != uid):
            return False
        text = message.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            return False
        now = time.monotonic()
        if now - self.last.get(uid, -100) < 2:
            return False
        self.last[uid] = now
        if uid not in self.agents:
            self.agents[uid] = self.factory(uid)
        self.api.send(uid, self.agents[uid].handle(text))
        return True

    def run(self):
        # Skip old queued commands: do not replay destructive actions after restart.
        updates = self.api.call('getUpdates', {'offset': -1, 'timeout': 0, 'allowed_updates': ['message']})
        offset = updates[-1]['update_id'] + 1 if updates else 0
        try:
            while True:
                updates = self.api.call('getUpdates', {'offset': offset, 'timeout': 25, 'allowed_updates': ['message']})
                for update in updates:
                    offset = update['update_id'] + 1
                    self.process(update)
        finally:
            for agent in self.agents.values():
                agent.db.close()
