# Push to GitHub - Quick Guide

## Your Repository
https://github.com/icigoat/link-to-file-bot.git

## Method 1: Using the Batch Script (Easiest)

Simply double-click:
```
push_to_github.bat
```

It will automatically:
1. Initialize git
2. Add all files
3. Commit
4. Push to your GitHub repo

## Method 2: Manual Commands

Open Command Prompt in this folder and run:

```bash
# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Telegram streaming proxy"

# Set main branch
git branch -M main

# Add your GitHub repository
git remote add origin https://github.com/icigoat/link-to-file-bot.git

# Push to GitHub
git push -u origin main
```

## Method 3: Using PowerShell

```powershell
git init
git add .
git commit -m "Initial commit: Telegram streaming proxy"
git branch -M main
git remote add origin https://github.com/icigoat/link-to-file-bot.git
git push -u origin main
```

## If You Get Authentication Error

GitHub requires a Personal Access Token (PAT) instead of password:

1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` (full control)
4. Copy the token
5. When git asks for password, paste the token

## After Pushing

Your code will be at:
https://github.com/icigoat/link-to-file-bot

## Next Steps: Deploy to Render

1. Go to https://dashboard.render.com/
2. Click "New +" → "Blueprint"
3. Connect to: https://github.com/icigoat/link-to-file-bot
4. Add environment variables:
   - TG_API_ID
   - TG_API_HASH
   - TG_SESSION_STRING
5. Click "Apply"

Your app will be live in 2-5 minutes!

## Update Code Later

After making changes:
```bash
git add .
git commit -m "Description of changes"
git push
```

Render will automatically redeploy!
