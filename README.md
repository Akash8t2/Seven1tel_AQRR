# Panel to Telegram Group Forwarder

Automatically forwards SMS from panel to Telegram groups with 24/7 uptime.

## Features
- Auto-login with CAPTCHA solving
- Forwards to multiple groups
- Number formatting options (with/without dots)
- Duplicate prevention
- OTP extraction and copy buttons
- Flask keep-alive server for 24/7 uptime

## Deploy to Render.com (FREE)

### 1. Push to GitHub
```bash
cd "e:\BOT BOLOD\PANEL TO GROUP"
git init
git add .
git commit -m "Panel to Telegram forwarder"
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

### 2. Deploy on Render.com
1. Go to [Render.com](https://render.com) and sign up
2. Click "New +" → "Web Service" (NOT Background Worker)
3. Connect your GitHub repository
4. Configure:
   - **Name**: panel-forwarder
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python panel_login.py`
   - **Instance Type**: Free
5. Click "Create Web Service"

### 3. Keep Alive with UptimeRobot (Optional)
1. Go to [UptimeRobot.com](https://uptimerobot.com)
2. Add New Monitor
3. Monitor Type: HTTP(s)
4. URL: Your Render app URL (e.g., https://panel-forwarder.onrender.com)
5. Monitoring Interval: Every 5 minutes

This will ping your bot every 5 minutes to keep it alive 24/7!

## Configuration
Edit `panel_login.py` and update:
- PANEL_USERNAME and PANEL_PASSWORD
- BOT_TOKEN
- GROUP_IDS_WITH_DOTS
- GROUP_IDS_WITHOUT_DOTS

## Local Testing
```bash
pip install -r requirements.txt
python panel_login.py
```

