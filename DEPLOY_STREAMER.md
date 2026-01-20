# Deploy TG File Streamer (Free Speed Boost) 🚀

## What This Does

The TG File Streamer is a **middleman service** that provides:
- ✅ **Optimized Range Requests** - Perfect seeking in VLC/MX Player
- ✅ **CORS Headers** - Works from any website
- ✅ **High-Speed Streaming** - No buffering issues
- ✅ **External Player Support** - Designed for VLC, MX Player, etc.

## 🆓 Free Deployment Options

### Option 1: Railway (Recommended)
**Why Railway**: Best for streaming, good free tier, easy setup

1. **Create Account**: Go to [railway.app](https://railway.app)
2. **Connect GitHub**: Link your GitHub account
3. **Create New Project**: Click "New Project" > "Deploy from GitHub repo"
4. **Upload Files**: Create a new repo with the `tg-streamer/` folder contents
5. **Set Environment Variables**:
   ```
   TG_API_ID=your_api_id
   TG_API_HASH=your_api_hash
   TG_SESSION_STRING=your_session_string
   ```
6. **Deploy**: Railway will auto-deploy
7. **Get URL**: Copy your Railway URL (e.g., `https://your-app.railway.app`)

### Option 2: Render.com
**Why Render**: Reliable, good for Python apps

1. **Create Account**: Go to [render.com](https://render.com)
2. **New Web Service**: Click "New" > "Web Service"
3. **Connect Repo**: Link your GitHub repo with `tg-streamer/` files
4. **Configure**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
5. **Environment Variables**: Add your Telegram credentials
6. **Deploy**: Wait for deployment
7. **Get URL**: Copy your Render URL

### Option 3: Fly.io
**Why Fly**: Good performance, generous free tier

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`
2. **Login**: `fly auth login`
3. **Navigate**: `cd tg-streamer`
4. **Initialize**: `fly launch`
5. **Set Secrets**:
   ```bash
   fly secrets set TG_API_ID=your_api_id
   fly secrets set TG_API_HASH=your_api_hash
   fly secrets set TG_SESSION_STRING=your_session_string
   ```
6. **Deploy**: `fly deploy`

## 🔧 Update Your Main App

After deploying, update your main app to use the external streamer:

1. **Find this line** in `templates/index.html`:
   ```javascript
   const externalUrl = url.replace('localhost:8000', 'your-streamer.railway.app');
   ```

2. **Replace with your actual URL**:
   ```javascript
   const externalUrl = url.replace('localhost:8000', 'your-actual-streamer-url.com');
   ```

## 🎯 How It Works

### Before (Slow):
```
VLC Player → Your Local Server → Telegram API
```
- Limited by your internet upload speed
- No proper range request handling
- Buffering issues

### After (Fast):
```
VLC Player → Cloud Streamer → Telegram API
```
- Cloud server bandwidth (much faster)
- Optimized range requests
- Perfect seeking and buffering

## 🚀 Speed Comparison

### Local Server:
- Upload limited (usually 1-10 Mbps)
- Buffering on large files
- Seeking issues

### Cloud Streamer:
- 100+ Mbps streaming
- Instant seeking
- No buffering
- Works like Netflix

## 🧪 Testing Your Streamer

### 1. Test Health Check
Visit: `https://your-streamer-url.com/`

Should return:
```json
{
  "service": "TG File Streamer",
  "status": "running",
  "version": "1.0.0"
}
```

### 2. Test File Info
Visit: `https://your-streamer-url.com/info/CHAT_ID/MESSAGE_ID`

Should return file information.

### 3. Test Streaming
Open in VLC: `https://your-streamer-url.com/stream/CHAT_ID/MESSAGE_ID`

## 🎬 Usage Examples

### VLC Network Stream:
```
https://your-streamer.railway.app/stream/-1001234567890/123
```

### MX Player URL:
```
https://your-streamer.railway.app/stream/@yourchannel/456
```

### Browser Streaming:
```javascript
// Your main app will automatically use the external streamer
// for VLC/MX Player buttons
```

## 🔒 Security Notes

- **Environment Variables**: Never commit credentials to GitHub
- **CORS**: The streamer allows all origins for compatibility
- **Rate Limiting**: Consider adding rate limiting for production
- **Session Security**: Use a dedicated session for the streamer

## 💡 Pro Tips

### Multiple Streamers
Deploy to multiple services for redundancy:
```javascript
const streamers = [
  'https://streamer1.railway.app',
  'https://streamer2.render.com',
  'https://streamer3.fly.dev'
];
// Use random streamer or failover logic
```

### Custom Domain
Most services allow custom domains:
- Railway: `stream.yourdomain.com`
- Render: `api.yourdomain.com`
- Fly: `files.yourdomain.com`

### Monitoring
Add uptime monitoring:
- UptimeRobot (free)
- Pingdom
- StatusCake

## 🎉 Result

After deployment, your users will experience:
- ✅ **Instant VLC opening** with perfect streaming
- ✅ **No buffering** even on large MKV files
- ✅ **Perfect seeking** - jump to any part instantly
- ✅ **Mobile compatibility** with MX Player
- ✅ **Professional experience** like Stremio/Netflix

Your Telegram File Browser now has **enterprise-grade streaming** powered by cloud infrastructure! 🚀