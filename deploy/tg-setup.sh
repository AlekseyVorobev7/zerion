#!/usr/bin/env bash
# Подключение Telegram-бота к форме. Запускать на сервере под root:
#   bash /opt/noctra/tg-setup.sh
# 1. Создайте бота у @BotFather и скопируйте токен.
# 2. Добавьте бота в нужный чат (или откройте личный диалог с ним) и отправьте любое сообщение.
# 3. Запустите скрипт: он спросит токен (ввод скрыт), сам найдёт chat_id и отправит тестовое сообщение.
set -euo pipefail

TOKEN=${TG_TOKEN:-}
if [ -z "$TOKEN" ]; then read -rsp "Токен бота: " TOKEN; echo; fi
[ -n "$TOKEN" ] || { echo "Токен пустой"; exit 1; }

UPDATES=$(curl -fsS "https://api.telegram.org/bot${TOKEN}/getUpdates") || { echo "Telegram отклонил токен"; exit 1; }
CHATS=$(printf '%s' "$UPDATES" | python3 -c '
import json, sys
seen = {}
for u in json.load(sys.stdin).get("result", []):
    m = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
    c = m.get("chat")
    if c:
        seen[c["id"]] = c.get("title") or c.get("username") or c.get("first_name") or ""
for i, t in seen.items():
    print(i, t)
')
[ -n "$CHATS" ] || { echo "Бот пока не видел ни одного сообщения. Напишите ему в нужном чате и запустите скрипт снова."; exit 1; }

echo "Найденные чаты:"; echo "$CHATS"
DEFAULT=$(printf '%s\n' "$CHATS" | tail -n1 | cut -d' ' -f1)
read -rp "chat_id [$DEFAULT]: " CHAT; CHAT=${CHAT:-$DEFAULT}

install -d -m 750 -o root -g www-data /etc/noctra
umask 077
printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$TOKEN" "$CHAT" > /etc/noctra/telegram.env
chown root:www-data /etc/noctra/telegram.env
chmod 640 /etc/noctra/telegram.env

systemctl restart noctra-api
curl -fsS -o /dev/null "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=NOCTRA: форма подключена" && echo "Готово, тестовое сообщение отправлено."
