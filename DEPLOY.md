# PuranGPT — Deployment & iOS App Guide

## Part 1 — Deploy Backend to Hetzner VPS

The backend and frontend are now deployed on a Hetzner VPS using Docker Compose.

### Step 1 — Connect to Hetzner
```bash
ssh -i ~/.ssh/purangpt_hetzner root@204.168.176.229
```

### Step 2 — Deploy Backend and Frontend
The codebase is located in `/root/purangpt` (backend) and `/root/purangpt-next` (frontend).

```bash
cd /root/purangpt
docker compose build backend
docker compose up -d backend

cd /root/purangpt-next
docker compose build frontend
docker compose up -d frontend
```

### Step 3 — Get your URL
The Next.js frontend is available at `http://204.168.176.229:3000`.
The FastAPI backend is available at `http://204.168.176.229:8000`.

Update `ios_app/build_ios.sh` → set `NEXT_PUBLIC_API_URL` to the Hetzner backend URL (`http://204.168.176.229:8000`).

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
