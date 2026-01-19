@echo off
echo Initializing Git repository...
git init

echo Adding all files...
git add .

echo Committing files...
git commit -m "Initial commit: Telegram streaming proxy"

echo Setting main branch...
git branch -M main

echo Adding remote repository...
git remote add origin https://github.com/icigoat/link-to-file-bot.git

echo Pushing to GitHub...
git push -u origin main

echo.
echo Done! Your code is now on GitHub.
echo Visit: https://github.com/icigoat/link-to-file-bot
pause
