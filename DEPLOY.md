# PuranGPT — Deployment & iOS App Guide

## Part 1 — Deploy Backend to Railway (free tier)

Railway is the simplest host for a FastAPI + Python backend. Free tier gives 500 hours/month.

### Step 1 — Create Railway account
1. Go to https://railway.app and sign up (free, GitHub login recommended)

### Step 2 — Push code to GitHub (if not already)
```bash
cd purangpt/
git init
git add .
git commit -m "initial"
git remote add origin https://github.com/YOUR_USERNAME/purangpt.git
git push -u origin main
```

### Step 3 — Create Railway project
1. In Railway dashboard → **New Project** → **Deploy from GitHub repo**
2. Select your repository
3. Railway auto-detects `Dockerfile.railway` → uses it

### Step 4 — Set environment variables in Railway
In Railway → your service → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `GEMINI_API_KEY` | your Gemini key (from aistudio.google.com) |
| `GROQ_API_KEY` | your Groq key (optional, Gemini works) |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_MODEL` | `gemini-2.5-flash` |
| `PORT` | `8000` |
| `HOST` | `0.0.0.0` |

### Step 5 — Add persistent volume (for data)
In Railway → your service → **Volumes** tab:
- Mount path: `/app/data`
- This persists your GRETIL texts, chunks, and ChromaDB index across deploys

### Step 6 — Upload your data to Railway volume
After first deploy, copy your local data up:
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway link   # select your project

# Copy local data to Railway volume
railway run -- bash -c "mkdir -p /app/data"
# Then scp or use Railway's file upload in the dashboard
```

### Step 7 — Get your URL
Railway assigns a URL like: `https://purangpt-production.up.railway.app`

Update `ios_app/ios_config.js` → set `DEPLOYED_API` to this URL.

---

## Part 2 — iOS App with Capacitor

Capacitor wraps your existing HTML/CSS/JS frontend into a native iOS app. No React Native, no rewrite.

### Prerequisites
- **Mac with Xcode 15+** installed (App Store → Xcode, ~15GB)
- **Node.js 18+** (`node --version`)
- **CocoaPods** (`sudo gem install cocoapods`)
- Apple Developer account (free for testing on your own device, $99/year for App Store)

### Step 1 — Install dependencies
```bash
cd purangpt/ios_app/
npm install
```

### Step 2 — Add `ios_config.js` to frontend HTML
Edit `frontend/index.html` — add this line **before** the `<script src="/static/app.js">` line:

```html
<!-- iOS API config — only active in native app -->
<script src="ios_config.js"></script>
```

Also copy `ios_config.js` into `frontend/`:
```bash
cp ios_app/ios_config.js frontend/ios_config.js
```

### Step 3 — Add iOS platform
```bash
cd ios_app/
npx cap add ios
```
This creates an `ios/` folder with a full Xcode project.

### Step 4 — Sync web assets
Every time you change the frontend, run:
```bash
npx cap sync
```
This copies `../frontend/` into the iOS app bundle.

### Step 5 — Open in Xcode and run
```bash
npx cap open ios
```
In Xcode:
1. Select your iPhone as target device (plug it in via USB)
2. Press ▶ (Run) — app installs on your phone
3. First run: go to iPhone Settings → General → VPN & Device Management → Trust your developer certificate

### Step 6 — App Store submission (when ready)
1. In Xcode: **Product → Archive**
2. Window → Organizer → Distribute App → App Store Connect
3. In App Store Connect (appstoreconnect.apple.com):
   - Create new app: "PuranGPT"
   - Bundle ID: `com.purangpt.app`
   - Category: Books / Education
   - Submit for review

---

## Part 3 — iOS App customisation

### Splash screen & icon
Replace these files in `ios_app/ios/App/App/Assets.xcassets/`:
- `AppIcon.appiconset/` — app icon (1024×1024 PNG, no alpha)
- `Splash.imageset/` — launch screen (2732×2732 PNG, dark background `#0B0907`)

### App name, description (for App Store)
- **Name:** PuranGPT
- **Subtitle:** AI Oracle of the Sacred Texts
- **Description:** Explore the 18 Mahapuranas, Vedas, Upanishads, and Yogic scriptures through AI-powered conversation. Every answer includes exact verse citations in Sanskrit and English.
- **Keywords:** puranas, vedas, upanishads, sanskrit, hinduism, bhagavad gita, yoga sutras, spiritual
- **Category:** Books

### Deep links (optional)
To share citations from the app, add to `capacitor.config.json`:
```json
"plugins": {
  "App": {
    "urlScheme": "purangpt"
  }
}
```
This enables URLs like `purangpt://cite/bhagavata/10.29.14` to open the app at a specific verse.

---

## Alternative — Render.com (easier than Railway for first deploy)

1. Go to https://render.com → New → Web Service
2. Connect GitHub repo
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python run.py`
5. **Environment:** Add same variables as Railway table above
6. Free tier: 750 hours/month, spins down after 15min inactivity (cold start ~30s)

## Alternative — Fly.io (best global performance)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

cd purangpt/
fly launch        # creates fly.toml automatically
fly secrets set GEMINI_API_KEY=your_key_here
fly secrets set GROQ_API_KEY=your_key_here
fly deploy
fly open          # opens your URL
```

Fly gives 3 free VMs with 256MB RAM — upgrade to 512MB for comfortable running.
