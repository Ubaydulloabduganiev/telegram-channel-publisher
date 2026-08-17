# Telegram Channel Publisher — Render + Scheduler

Telegram kanaliga rasm/video postlarini yuborish, ko'rib chiqish va oldindan
rejalashtirish uchun bot.

## Asosiy imkoniyatlar

- Bot interfeysi to'liq o'zbek tilida.
- Rasm + caption.
- Video + caption.
- Telegram formatlash elementlarini saqlaydi.
- Postni avval preview qiladi.
- `✅ Hozir joylash`.
- `🗓 Vaqtga rejalashtirish`.
- `✏️ Matnni tahrirlash`.
- `🗑 Bekor qilish`.
- Postlarni 31 kun oldindan rejalashtirish.
- Vaqt zonasi: `Asia/Tashkent` (UTC+5).
- `/reja` orqali yaqin rejalashtirilgan postlarni ko'rish.
- Rejadagi postni bekor qilish.
- PostgreSQL da persistent saqlash.
- Render Cron worker orqali avtomatik jo'natish.
- Xato bo'lsa 5 martagacha avtomatik qayta urinish.
- Rejalashtirilgan post joylanganda admin Telegramiga tasdiq yuborish.
- Webhook rejimi — Render Web Service uchun.

## Scheduler qanday ishlaydi?

1. Botga rasm/video yuborasiz.
2. Bot Telegram `file_id`, caption va vaqtni PostgreSQL bazasiga yozadi.
3. Siz Toshkent vaqti bilan sana/vaqt kiritasiz.
4. Render Cron Job har daqiqada `scheduler_worker.py` ni ishga tushiradi.
5. Vaqti kelgan postlar Telegram kanaliga avtomatik yuboriladi.

Bot media faylning o'zini Render diskida saqlamaydi. Telegram `file_id` qayta ishlatiladi.

## Environment variables

Web Service:

```env
BOT_TOKEN=...
CHANNEL_ID=@channel
ADMIN_IDS=123456789
DATABASE_URL=postgresql://...
```

Cron Job:

```env
BOT_TOKEN=...
CHANNEL_ID=@channel
DATABASE_URL=postgresql://...
```

## Render Web Service

Build:

```text
pip install -r requirements.txt
```

Start:

```text
python app.py
```

Health:

```text
/health
```

## Render Cron Job

Repository shu repo.

Build command:

```text
pip install -r requirements.txt
```

Command:

```text
python scheduler_worker.py
```

Schedule:

```text
* * * * *
```

Render cron expressions UTC da ishlaydi, lekin bu cron har daqiqada ishlagani uchun
bot ichida saqlangan UTC vaqt bilan postlarni topadi. Foydalanuvchi esa sanani
Toshkent vaqti bilan kiritadi.

## Sana formati

```text
25.08.2026 18:30
```

yoki joriy yil uchun:

```text
25.08 18:30
```

Eng uzoq muddat: 31 kun.

## Buyruqlar

- `/start` — yordam
- `/reja` — navbatdagi rejalashtirilgan postlar
- `/status` — webhook, kanal va scheduler holati
- `/myid` — Telegram ID

## Muhim: Render persistence

Scheduler uchun local SQLite ishlatilmaydi. Render Web Service fayl tizimi ephemeral
bo'lgani uchun PostgreSQL kerak.

Productionda uzoq muddatli scheduler uchun muddati tugamaydigan persistent PostgreSQL ishlating.
