# Telegram Channel Publisher — Render Edition

A private admin Telegram bot for publishing photo/video posts with captions to a Telegram channel. This edition is designed for Render Web Services and uses Telegram webhooks instead of long polling.

## Features

- Photo + caption publishing
- Video + caption publishing
- Media can be sent without a caption and edited before publishing
- Private preview before anything is sent to the channel
- Publish / Edit caption / Cancel buttons
- Telegram-native caption entities and formatting are preserved
- Reuses Telegram `file_id` values instead of downloading and re-uploading media
- Admin-only access, with support for multiple admins
- `/status` checks the webhook and channel posting permission
- `/myid` shows your Telegram user ID
- Health endpoint for Render
- Automatically registers the Telegram webhook using Render's `RENDER_EXTERNAL_URL`
- Webhook requests are protected with Telegram's `secret_token`
- No local SQLite dependency for the normal preview → edit → publish flow

## Why this version is stateless

Render free Web Services use an ephemeral local filesystem. To avoid losing draft data after a restart or redeploy, the Telegram preview message itself acts as the draft. Caption editing is linked back to the preview message without requiring a local database.

## Deploy to Render

### 1. Create the Telegram bot

1. Open `@BotFather` in Telegram.
2. Send `/newbot`.
3. Create the bot and copy its token.
4. Keep the token private.

### 2. Add the bot to your channel

Open your Telegram channel and go to:

**Channel → Administrators → Add Administrator**

Add the bot and enable permission to **Post Messages**.

### 3. Configure Render

This repository includes `render.yaml`, so the easiest route is a Render Blueprint:

1. Sign in to Render.
2. Choose **New → Blueprint**.
3. Connect this GitHub repository.
4. Render detects `render.yaml`.
5. Add these environment variables when Render asks for them:

```text
BOT_TOKEN=your_botfather_token
CHANNEL_ID=@your_channel_username
ADMIN_IDS=your_telegram_user_id
```

For multiple admins:

```text
ADMIN_IDS=123456789,987654321
```

For a private Telegram channel, `CHANNEL_ID` may be a numeric channel ID such as:

```text
-1001234567890
```

Do not commit a real `.env` file or your real token. `.env` is ignored by Git.

### 4. Test after deployment

Open the bot and send:

```text
/status
```

You want the bot to report that the webhook and channel posting permission are valid.

Then send a photo or video with its caption. The bot creates a preview. Press:

```text
✅ Publish to channel
```

Nothing is posted to the actual channel until you press Publish.

## Render endpoints

- `/` — basic running message
- `/health` — JSON health check used by Render
- `/telegram/webhook` — Telegram webhook endpoint

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `BOT_TOKEN` | Yes | Token from `@BotFather` |
| `CHANNEL_ID` | Yes | Target Telegram channel username or numeric ID |
| `ADMIN_IDS` | Yes | Comma-separated Telegram user IDs allowed to control the bot |
| `RENDER_EXTERNAL_URL` | Automatic on Render | Public Render URL used for webhook registration |
| `PUBLIC_BASE_URL` | Local testing only | Optional public URL when testing outside Render |
| `PORT` | Automatic on Render | Port used by the web service |

## Commands

- `/start` — bot instructions
- `/status` — check webhook and channel permissions
- `/myid` — show your Telegram user ID

## Current limitation

Telegram media albums are deliberately rejected. The current build supports one photo or one video per post so an album cannot accidentally be split into separate channel posts.

## Security

- Never commit your real bot token.
- Keep `.env` out of GitHub.
- Limit `ADMIN_IDS` to trusted Telegram accounts.
- The real secrets should be stored only in Render Environment Variables.
