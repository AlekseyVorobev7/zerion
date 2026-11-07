#!/usr/bin/env python3
"""Приём заявок с формы NOCTRA и отправка их в Telegram-чат.

Только стандартная библиотека. Слушает 127.0.0.1:8081, nginx проксирует /api/ сюда.
Секреты берутся из окружения (файл /etc/noctra/telegram.env):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = '127.0.0.1', 8081
MAX_BODY = 10_000
LIMIT, WINDOW = 5, 3600          # не больше 5 заявок в час с одного IP
EMAIL_RE = re.compile(r'^\S+@\S+\.\S+$')
hits = defaultdict(deque)


def allowed(ip):
    now = time.time()
    q = hits[ip]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return False
    q.append(now)
    return True


def send_via_relay(name, email, message, ip):
    """Если api.telegram.org недоступен с сервера, шлём через Cloudflare Worker."""
    data = json.dumps({'name': name, 'email': email, 'message': message, 'ip': ip}).encode()
    req = urllib.request.Request(
        os.environ['RELAY_URL'], data=data,
        headers={'Content-Type': 'application/json',
                 'X-Relay-Secret': os.environ.get('RELAY_SECRET', ''),
                 'User-Agent': 'noctra-api'})
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status != 200:
            raise RuntimeError(f'relay status {r.status}')


def send_telegram(name, email, message, ip):
    if os.environ.get('RELAY_URL'):
        return send_via_relay(name, email, message, ip)
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat:
        raise RuntimeError('telegram is not configured')
    text = (
        '<b>Новая заявка NOCTRA</b>\n\n'
        f'<b>Имя:</b> {html.escape(name)}\n'
        f'<b>Email:</b> {html.escape(email)}\n\n'
        f'<b>Задача:</b>\n{html.escape(message)}\n\n'
        f'<i>IP: {html.escape(ip)}</i>'
    )
    data = json.dumps({'chat_id': chat, 'text': text, 'parse_mode': 'HTML',
                       'disable_web_page_preview': True}).encode()
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage', data=data,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status != 200:
            raise RuntimeError(f'telegram status {r.status}')


class Handler(BaseHTTPRequestHandler):
    server_version = 'noctra-api'

    def log_message(self, fmt, *args):      # без IP и тел запросов в логах
        print('%s %s' % (self.command, self.path), flush=True)

    def reply(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != '/api/lead':
            return self.reply(404, {'ok': False})
        ip = self.headers.get('X-Real-IP') or self.client_address[0]
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.reply(413, {'ok': False, 'error': 'bad size'})
            data = json.loads(self.rfile.read(size))
        except (ValueError, TypeError):
            return self.reply(400, {'ok': False, 'error': 'bad json'})

        if data.get('website'):             # honeypot: боты заполняют скрытое поле
            return self.reply(200, {'ok': True})
        name = str(data.get('name', '')).strip()[:100]
        email = str(data.get('email', '')).strip()[:150]
        message = str(data.get('message', '')).strip()[:3000]
        if not name or not message or not EMAIL_RE.match(email):
            return self.reply(422, {'ok': False, 'error': 'validation'})
        if not allowed(ip):
            return self.reply(429, {'ok': False, 'error': 'rate limit'})
        try:
            send_telegram(name, email, message, ip)
        except (RuntimeError, urllib.error.URLError, OSError) as e:
            print('telegram error:', type(e).__name__, flush=True)
            return self.reply(502, {'ok': False, 'error': 'delivery'})
        self.reply(200, {'ok': True})


if __name__ == '__main__':
    print(f'noctra-api on {HOST}:{PORT}', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
