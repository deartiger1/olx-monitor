# OLX 1BHK Rental Monitor

Get instant iPhone push notifications the moment a new 1BHK rental is posted on OLX.  
Tap the notification → opens directly in your **OLX app**.

---

## How it works

```
Railway (Python script runs 24/7)
    ↓  scrapes OLX every 5 min
    ↓  finds new listings
    ↓  posts to ntfy.sh (free push service)
        ↓
      iPhone notification
        ↓  tap it
      OLX app opens the exact listing
```

---

## Step 1 — Install ntfy on your iPhone

1. Open the **App Store** and search for **ntfy**
2. Install the free app by Philipp Heckel
3. Open it — you'll subscribe to your topic in Step 3

---

## Step 2 — Choose your secret topic name

Your topic is like a private channel. Make it hard to guess so only you get alerts.

Good example: `olx-1bhk-ramesh-k47x9`  
Bad example: `olx-alerts` (too guessable, others might subscribe)

**Write it down** — you'll need it in Step 3 and Step 5.

---

## Step 3 — Subscribe in the ntfy app

1. Open the ntfy app on your iPhone
2. Tap **+** (top right)
3. Enter your topic name, e.g. `olx-1bhk-ramesh-k47x9`
4. Tap **Subscribe**
5. When iOS asks about notifications, tap **Allow**

---

## Step 4 — Deploy to Railway (free hosting)

Railway gives you $5 free credit/month — more than enough for this script.

### 4a. Create a GitHub repository

1. Go to [github.com](https://github.com) and create a free account if needed
2. Click **New repository** → name it `olx-monitor`
3. Upload these 4 files: `monitor.py`, `requirements.txt`, `railway.toml`, `README.md`

### 4b. Deploy on Railway

1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `olx-monitor` repository
4. Railway will auto-detect Python and start building

---

## Step 5 — Set your environment variables on Railway

In your Railway project, go to **Variables** and add these:

| Variable         | Example value              | Description                          |
|-----------------|---------------------------|--------------------------------------|
| `NTFY_TOPIC`    | `olx-1bhk-ramesh-k47x9`   | **Required.** Your secret topic name |
| `AREAS`         | `Kakkanad,Edapally,Aluva` | Comma-separated areas to monitor     |
| `BUDGET_MIN`    | `7000`                    | Minimum monthly rent in ₹            |
| `BUDGET_MAX`    | `18000`                   | Maximum monthly rent in ₹            |
| `FURNISHED`     | `any`                     | `any` / `furnished` / `unfurnished`  |
| `CHECK_INTERVAL`| `300`                     | Seconds between scans (300 = 5 min)  |

After saving variables, Railway will restart the service automatically.

---

## Step 6 — Verify it's working

1. Check Railway **Logs** tab — you should see:
   ```
   OLX 1BHK Rental Monitor starting…
   Areas: ['Kakkanad', 'Edapally', 'Aluva']
   ```
2. Within a minute, your iPhone should receive a notification:
   **"OLX Monitor is live! ✅"**

3. When a new 1BHK listing is found, you'll get:
   ```
   New 1BHK · Kakkanad · ₹12,000/mo
   Spacious 1BHK flat near Infopark, Kakkanad
   ```
   → Tap it → OLX app opens the exact listing

---

## Notification behaviour on iPhone

- Notifications arrive within ~5 minutes of a listing being posted
- Tapping the notification body opens the OLX listing in the **OLX app** (iOS universal link)
- The notification also has an **"Open in OLX"** action button
- You can set ntfy notification sounds, badges, and critical alerts in the ntfy app settings

---

## Customising areas

Update the `AREAS` variable on Railway any time. Format: comma-separated, no spaces around commas.

Examples:
```
Kakkanad,Edapally,Aluva,Thrippunithura
Koramangala,Indiranagar,HSR Layout
Baner,Wakad,Hinjewadi
```

---

## Troubleshooting

**Not getting notifications?**
- Check Railway logs for errors
- Make sure the ntfy topic name matches exactly in both Railway env vars and the ntfy app
- Check iPhone Settings → Notifications → ntfy → Allow Notifications is ON

**Getting too many notifications?**
- Narrow your `AREAS` list
- Tighten your `BUDGET_MIN` / `BUDGET_MAX`
- Increase `CHECK_INTERVAL` to `600` (10 min)

**Listings page changed / no listings found?**
- OLX occasionally updates their HTML structure
- Check Railway logs — the script will log how many listings it found per area
- Open an issue on your GitHub repo and update the parser if needed

---

## Cost

| Service  | Cost      |
|----------|-----------|
| Railway  | Free ($5/month credit, script uses ~$0.50) |
| ntfy.sh  | Free      |
| ntfy app | Free      |
| **Total** | **₹0**   |

---

## Files in this project

```
olx-monitor/
├── monitor.py        ← main script (edit areas/budget here or use env vars)
├── requirements.txt  ← Python packages
├── railway.toml      ← Railway deployment config
└── README.md         ← this file
```
