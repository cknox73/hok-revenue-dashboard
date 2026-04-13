# 💰 HoK Revenue Dashboard

Unified view of all House of Knox income streams: **Gumroad**, **Stripe**, and **Affiliate** clicks.

Live dashboard: https://hok-revenue-dashboard.streamlit.app

---

## Features

- **Total revenue** (Gumroad + Stripe) — month-to-date and all-time
- **Revenue over time** — stacked bar chart (last 30 days)
- **Revenue by product** — Gumroad product breakdown
- **Revenue by channel** — Pie chart (Gumroad vs Stripe)
- **Recent transactions** — last 50 sales/payments
- **Affiliate links** — tracked clicks per tool

---

## Deploy to Streamlit Cloud

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "HoK Revenue Dashboard"
   git remote add origin https://github.com/YOUR_USERNAME/hok-revenue-dashboard.git
   git push -u origin main
   ```

2. **Connect repo to Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - "New app" → select this repo → branch `main`
   - Main file: `streamlit_app.py`

3. **Add secrets** (in Streamlit Cloud settings)
   ```
   GUMROAD_TOKEN = your_gumroad_bearer_token
   STRIPE_SECRET_KEY = sk_live_...
   ```

4. **Deploy** — app will be live in ~2 minutes

---

## Local Development

```bash
cd hok-revenue-dashboard
pip install -r requirements.txt

# Set environment variables
export GUMROAD_TOKEN=your_token
export STRIPE_SECRET_KEY=sk_live_...

streamlit run streamlit_app.py
```

---

## Data Sources

| Source | Method | Refresh |
|--------|--------|---------|
| Gumroad sales | Gumroad REST API v2 | Every 5 min (cached) |
| Stripe payments | Stripe API (PaymentIntents) | Every 5 min (cached) |
| Affiliate clicks | Local `affiliate_tracker.json` | Every 5 min (cached) |
