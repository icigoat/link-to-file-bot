# Deploy to Render - Step by Step Guide

## Prerequisites
- GitHub account
- Render account (free tier works)
- Your Telegram credentials ready

## Step 1: Push Code to GitHub

1. Create a new repository on GitHub (e.g., `telegram-streaming-proxy`)
2. Initialize git in your project folder:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/telegram-streaming-proxy.git
git push -u origin main
```

## Step 2: Deploy on Render

### Option A: Using render.yaml (Recommended)

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. Click **"Apply"**

### Option B: Manual Setup

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `telegram-streaming-proxy`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: `Free` (or paid for better performance)

## Step 3: Add Environment Variables

In Render dashboard, go to your service → **Environment** tab:

Add these variables:
```
TG_API_ID = 39693321
TG_API_HASH = 7be8afb3ebde3a05a58323af198a64bf
TG_SESSION_STRING = BQJdrAkAHhSZbVAD7ugR_4JwusW91gbeJFSUQsWtic-OydS9g7eGbhHEM4zGGo0Nkli5HknlWgdkVYi9lF4LDDXnXfOmRXXlf6eXEUaJbKSWnxy7ngND1CPCNzDcui2k6drOmD7ng0VqEAWVp7c7D7hUSe36MjJT_C3vYgtjifCFk2Zq-N6yvToSy4j9sP71Lz3NHVReGVGh3d9JXVY0PO4qL0RIKPVfn2GtHxUQGk7ay7bj3UkW6A-EmtBZ7_ZP6lLWfugbCFLcFI2hUFSRjGcHOJmpb99eOMqCnUoiIYf4eP6Ltk3IDmh8YMAADbDVrUDa99TV8ffxTdgSE468Kz7AecUDjAAAAAHdV6YgAA
```

**Important**: Don't commit these to GitHub! Only add them in Render's dashboard.

## Step 4: Deploy

1. Click **"Create Web Service"** or **"Apply"**
2. Render will build and deploy your app
3. Wait 2-5 minutes for deployment
4. You'll get a URL like: `https://telegram-streaming-proxy.onrender.com`

## Step 5: Test Your Deployment

Visit your Render URL:
```
https://your-app-name.onrender.com/
```

You should see:
```json
{
  "status": "online",
  "service": "Telegram Streaming Proxy",
  "usage": "/dl/{channel_id}/{message_id}"
}
```

## How to Use After Deployment

### Download Files
```
https://your-app-name.onrender.com/dl/{channel_id}/{message_id}
```

**Examples:**
- Public channel: `https://your-app-name.onrender.com/dl/@channelname/123`
- Private channel: `https://your-app-name.onrender.com/dl/-1001234567890/456`

## Important Notes for Render

### Free Tier Limitations
- **Spins down after 15 minutes of inactivity**
- First request after spin-down takes ~30 seconds to wake up
- 750 hours/month free (enough for one service)
- Shared CPU and 512MB RAM

### Paid Tier Benefits ($7/month)
- Always running (no spin-down)
- Better performance
- More RAM and CPU
- Recommended for production use

### Session Persistence
- Your Telegram session stays active even when the service spins down
- The session string keeps you logged in
- No need to re-authenticate

### Bandwidth
- Render doesn't charge for bandwidth on free tier
- Files stream directly: Telegram → Render → User
- Zero disk usage (all streaming)

## Troubleshooting

### Service won't start
- Check logs in Render dashboard
- Verify environment variables are set correctly
- Ensure no spaces in SESSION_STRING

### "Access denied" errors
- Verify your session string is valid
- Check if your account has access to the channel
- For private channels, use numeric ID with -100 prefix

### Slow downloads
- Free tier has limited resources
- Consider upgrading to paid tier
- Check if Telegram is rate-limiting your account

## Security Tips

1. **Never commit credentials to GitHub**
2. **Use environment variables only**
3. **Regenerate session if compromised**
4. **Consider adding authentication** (API key) for production

## Monitoring

Check your service health:
- Render Dashboard → Logs
- Render Dashboard → Metrics
- Set up alerts for downtime

## Updating Your Service

Push changes to GitHub:
```bash
git add .
git commit -m "Update description"
git push
```

Render will automatically redeploy!

---

**Your service is now live and ready to stream Telegram files! 🚀**
