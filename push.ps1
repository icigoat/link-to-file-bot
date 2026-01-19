# Push to GitHub Script
Write-Host "Pushing to GitHub..." -ForegroundColor Green

# Initialize git
Write-Host "`nStep 1: Initializing git..." -ForegroundColor Yellow
git init

# Add all files
Write-Host "`nStep 2: Adding files..." -ForegroundColor Yellow
git add .

# Commit
Write-Host "`nStep 3: Committing..." -ForegroundColor Yellow
git commit -m "Initial commit: Telegram streaming proxy"

# Set main branch
Write-Host "`nStep 4: Setting main branch..." -ForegroundColor Yellow
git branch -M main

# Add remote
Write-Host "`nStep 5: Adding remote repository..." -ForegroundColor Yellow
git remote add origin https://github.com/icigoat/link-to-file-bot.git

# Push
Write-Host "`nStep 6: Pushing to GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host "`nDone! Check: https://github.com/icigoat/link-to-file-bot" -ForegroundColor Green
