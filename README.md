# Telegram Streaming Proxy

High-performance streaming proxy that converts Telegram files into direct HTTP download links using FastAPI and Pyrogram.

## Quick Deploy to Render

1. **Push to GitHub:**
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/telegram-streaming-proxy.git
git push -u origin main
```

2. **Deploy on Render:**
   - Go to [Render Dashboard](https://dashboard.render.com/)
   - Click "New +" → "Blueprint"
   - Connect your GitHub repo
   - Add environment variables in dashboard:
     - `TG_API_ID`
     - `TG_API_HASH`
     - `TG_SESSION_STRING`
   - Click "Apply"

3. **Done!** Your URL: `https://your-app-name.onrender.com`

See [RENDER_DEPLOY.md](RENDER_DEPLOY.md) for detailed instructions.

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create `.env` file:
```
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_SESSION_STRING=your_session_string
PORT=8000
```

3. Run:
```bash
python main.py
```

## Usage

### Check Status
```
GET /
```

### Download File
```
GET /dl/{chat_id}/{message_id}
```

**Examples:**
- Public channel: `/dl/@channelname/123`
- Private channel: `/dl/-1001234567890/456`

## Get Channel/Message IDs

Run the helper script:
```bash
python get_ids.py
```

This will list your channels and recent messages with download URLs.

## Features

- Zero disk usage (pure streaming)
- Handles concurrent downloads
- Supports all Telegram media types
- Automatic file type detection
- Proper HTTP headers (Content-Disposition, Content-Type, Content-Length)

## How It Works on Render

1. **Request comes in**: User visits your Render URL with channel/message ID
2. **Pyrogram connects**: Your app authenticates with Telegram using session string
3. **Streaming starts**: File chunks stream from Telegram → Render → User's browser
4. **Zero storage**: Nothing saved to disk, pure memory streaming

### Free Tier Notes
- Service spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds (cold start)
- Session persists even when spun down
- 750 hours/month free

### Paid Tier ($7/month)
- Always running (no cold starts)
- Better performance
- Recommended for production

## License

MIT
