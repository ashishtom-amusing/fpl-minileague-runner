# FPL Gameweek Leaderboard

Flask web app to display Fantasy Premier League gameweek leaderboards.

## Files Structure
```
├── app.py              # Flask application
├── templates/
│   └── index.html      # Frontend UI
├── requirements.txt    # Python dependencies
└── render.yaml         # Render deployment config
```

## Deployment Steps (GitHub + Render)

### 1. GitHub Setup
```bash
# Initialize git repo
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/fpl-leaderboard.git
git branch -M main
git push -u origin main
```

### 2. Render Deployment
1. Go to https://render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub account
4. Select your `fpl-leaderboard` repository
5. Render will auto-detect `render.yaml`
6. Click "Create Web Service"
7. Wait for deployment (2-3 minutes)

### 3. Access Your App
- URL: `https://fpl-leaderboard.onrender.com` (or your custom name)

## How to Use
1. Enter **Gameweek** number (1-38)
2. Enter **League ID** (find it in your FPL league URL)
3. Click "Fetch Data"
4. View leaderboard sorted by gameweek points

## Environment
- Python 3.11
- Flask web framework
- Gunicorn production server
- FPL API integration

## Notes
- Free tier on Render may sleep after inactivity (takes 30s to wake)
- Upgrade to paid tier for 24/7 availability
- League data updates in real-time from FPL API
