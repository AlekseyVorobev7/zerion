// Cloudflare Worker: пересылает заявки с сервера в Telegram.
// Сервер не может достучаться до api.telegram.org, поэтому ходит сюда.
//
// Переменные воркера (Settings -> Variables and Secrets):
//   BOT_TOKEN     токен бота от @BotFather (Secret)
//   CHAT_ID       id чата для заявок (Text)
//   RELAY_SECRET  общий секрет с сервером, заголовок X-Relay-Secret (Secret)

const esc = (s) => String(s ?? '').replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

export default {
  async fetch(req, env) {
    if (req.method !== 'POST') return new Response('method not allowed', { status: 405 });
    if (req.headers.get('X-Relay-Secret') !== env.RELAY_SECRET) return new Response('forbidden', { status: 403 });

    let d;
    try { d = await req.json(); } catch { return new Response('bad json', { status: 400 }); }

    const text =
      '<b>Новая заявка NOCTRA</b>\n\n' +
      `<b>Имя:</b> ${esc(d.name).slice(0, 100)}\n` +
      `<b>Email:</b> ${esc(d.email).slice(0, 150)}\n\n` +
      `<b>Задача:</b>\n${esc(d.message).slice(0, 3000)}\n\n` +
      `<i>IP: ${esc(d.ip).slice(0, 64)}</i>`;

    const r = await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: env.CHAT_ID, text, parse_mode: 'HTML', disable_web_page_preview: true }),
    });
    return new Response(null, { status: r.ok ? 200 : 502 });
  },
};
