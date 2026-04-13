"""
House of Knox — Revenue Dashboard
One view of all income streams: Gumroad, Stripe, Affiliate.
Deployed on Streamlit Cloud.

Secrets (set in Streamlit Cloud settings):
  GUMROAD_TOKEN    — your Gumroad API bearer token
  STRIPE_SECRET_KEY — your Stripe secret key (sk_live_...)
"""

import streamlit as st
import json
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HoK Revenue Dashboard",
    page_icon="💰",
    layout="wide",
)

# ─── CREDENTIALS (Streamlit Secrets or environment) ────────────────────────────
# Streamlit Cloud: set these in Settings > Secrets
# Local: set in .env or shell environment
GUMROAD_TOKEN    = None
STRIPE_SECRET_KEY = None

try:
    GUMROAD_TOKEN    = st.secrets["GUMROAD_TOKEN"]
    STRIPE_SECRET_KEY = st.secrets["STRIPE_SECRET_KEY"]
except Exception:
    # Fallback to environment variables (local dev)
    GUMROAD_TOKEN    = os.environ.get("GUMROAD_TOKEN", "")
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

APP_DIR = Path(__file__).parent.resolve()

# ─── STYLING ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stMetric { background: #111; border: 1px solid #222; border-radius: 8px; padding: 16px 24px; }
    .stMetric label { color: #888 !important; font-size: 13px !important; text-transform: uppercase; letter-spacing: 0.06em; }
    .stMetric [data-testid="stMetricValue"] { color: #f5f5f0 !important; font-size: 28px !important; font-weight: 700 !important; }
    .section-header { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #c9a84c; margin-bottom: 8px; font-weight: 600; }
    .kpi-card { background: #111; border: 1px solid #222; border-radius: 8px; padding: 20px 24px; }
    .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #666; margin: 0 0 4px 0; }
    .kpi-value { font-size: 32px; font-weight: 700; color: #f5f5f0; margin: 0; }
    .kpi-sub { font-size: 12px; color: #555; margin: 4px 0 0 0; }
    .divider { border: none; border-top: 1px solid #222; margin: 24px 0; }
    .stException { background: #1a1a1a; border: 1px solid #333; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ─── DATA: GUMROAD ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_gumroad_data():
    """Fetch sales directly from Gumroad API (no local DB needed)"""
    if not GUMROAD_TOKEN:
        return []
    all_sales = []
    page_key = None
    try:
        while len(all_sales) < 200:
            params = {"per_page": 100}
            if page_key:
                params["page_key"] = page_key
            r = requests.get(
                "https://api.gumroad.com/v2/sales",
                headers={"Authorization": f"Bearer {GUMROAD_TOKEN}"},
                params=params,
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
            sales = data.get("sales", [])
            if not sales:
                break
            all_sales.extend(sales)
            page_key = data.get("next_page_key")
            if not page_key:
                break
    except Exception as e:
        st.warning(f"Gumroad API error: {e}")
    return all_sales


# ─── DATA: STRIPE ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stripe_data():
    """Fetch payment intents from Stripe API"""
    if not STRIPE_SECRET_KEY:
        return []
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        since = datetime.now(timezone.utc) - timedelta(days=365)  # last year
        pis = stripe.PaymentIntent.list(
            created={"gte": int(since.timestamp())},
            limit=100,
        )
        return [
            {
                "id": pi.id,
                "amount": pi.amount / 100,
                "currency": pi.currency.upper(),
                "status": pi.status,
                "created": datetime.fromtimestamp(pi.created, tz=timezone.utc).isoformat(),
                "description": pi.description or "Review Responder",
                "customer_email": pi.receipt_email or "",
            }
            for pi in pis.data
        ]
    except Exception as e:
        st.warning(f"Stripe API error: {e}")
        return []


# ─── DATA: AFFILIATE ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_affiliate_data():
    """Load affiliate tracker if present (local file for click tracking)"""
    tracker_path = APP_DIR / "affiliate_tracker.json"
    if not tracker_path.exists():
        return {"clicks": {}, "conversions": {}}
    try:
        with open(tracker_path) as f:
            return json.load(f)
    except Exception:
        return {"clicks": {}, "conversions": {}}


AFFILIATE_LINKS = {
    "claude":      {"name": "Claude",        "url": "https://claude.ai/invite/tqK3NqJxHN6gQZi2K", "reward": "$50/user"},
    "anthropic":   {"name": "Anthropic API", "url": "https://www.anthropic.com/api",            "reward": "20% for 3mo"},
    "openai":      {"name": "OpenAI API",    "url": "https://platform.openai.com",               "reward": "30d credits"},
    "stripe":      {"name": "Stripe",         "url": "https://stripe.com/referrals",              "reward": "$50/sale"},
    "beehiiv":     {"name": "Beehiiv",       "url": "https://www.beehiiv.com",                   "reward": "$10/referral"},
    "perplexity":  {"name": "Perplexity",    "url": "https://perplexity.ai/pro",                 "reward": "$10 credit"},
    "render":      {"name": "Render",        "url": "https://render.com",                        "reward": "$100/paying"},
    "semrush":     {"name": "SEMrush",        "url": "https://semrush.com",                      "reward": "200 EUR + 30%"},
}


# ─── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    st.markdown("## 💰 House of Knox — Revenue Dashboard")
    st.caption(f"Refreshes every 5 min · Updated {datetime.now().strftime('%d %b %Y, %H:%M')} BST")

    # ── Load all data ─────────────────────────────────────────────────────────
    gumroad_sales    = get_gumroad_data()
    stripe_payments  = get_stripe_data()
    affiliate_data   = get_affiliate_data()

    # ── KPI calculations ───────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def to_dt(ts_str):
        try:
            return datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        except Exception:
            return this_month_start

    # Gumroad
    gumroad_paid = [s for s in gumroad_sales if s.get("paid", False) is True]
    gumroad_month = [
        s for s in gumroad_paid
        if to_dt(s.get("created_at", "")) >= this_month_start
    ]
    # Price is in cents; Gumroad returns formatted_total_price or price in cents
    def gumroad_amount(sale):
        price = sale.get("price", 0)
        if price and price > 0:
            return price / 100
        # Try parse formatted price like "£9.99"
        fmt = sale.get("formatted_total_price", "")
        if fmt:
            try:
                return float(fmt.replace("£", "").replace("$", "").replace(",", ""))
            except Exception:
                pass
        return 0

    gumroad_month_revenue = sum(gumroad_amount(s) for s in gumroad_month)
    gumroad_total_revenue = sum(gumroad_amount(s) for s in gumroad_paid)
    gumroad_total_count  = len(gumroad_paid)

    # Stripe
    stripe_succeeded  = [p for p in stripe_payments if p["status"] == "succeeded"]
    stripe_month      = [
        p for p in stripe_succeeded
        if to_dt(p["created"]) >= this_month_start
    ]
    stripe_month_revenue  = sum(p["amount"] for p in stripe_month)
    stripe_total_revenue   = sum(p["amount"] for p in stripe_succeeded)

    # Affiliate
    affiliate_clicks    = sum(affiliate_data.get("clicks", {}).values())
    affiliate_convs     = sum(affiliate_data.get("conversions", {}).values())

    # ── KPI CARDS ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<p class="kpi-label">Gumroad — This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{gumroad_month_revenue:,.2f}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{len(gumroad_month)} sale{"s" if len(gumroad_month) != 1 else ""} · £{gumroad_month_revenue/max(len(gumroad_month),1):.2f} avg</p>', unsafe_allow_html=True)

    with col2:
        st.markdown('<p class="kpi-label">Stripe — This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{stripe_month_revenue:,.2f}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{len(stripe_month)} payment{"s" if len(stripe_month) != 1 else ""}</p>', unsafe_allow_html=True)

    with col3:
        combined_month = gumroad_month_revenue + stripe_month_revenue
        st.markdown('<p class="kpi-label">Combined — This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{combined_month:,.2f}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{len(gumroad_month)+len(stripe_month)} total transactions</p>', unsafe_allow_html=True)

    with col4:
        st.markdown('<p class="kpi-label">Affiliate Clicks</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">{affiliate_clicks}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{affiliate_convs} conversions · {len(AFFILIATE_LINKS)} links tracked</p>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── REVENUE OVER TIME ─────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Revenue Over Time — Last 30 Days</p>', unsafe_allow_html=True)

    last_30 = now.date() - timedelta(days=30)

    gumroad_by_day = {}
    for s in gumroad_paid:
        dt = to_dt(s.get("created_at", "")).date()
        if dt >= last_30:
            gumroad_by_day[dt] = gumroad_by_day.get(dt, 0) + gumroad_amount(s)

    stripe_by_day = {}
    for p in stripe_succeeded:
        dt = to_dt(p["created"]).date()
        if dt >= last_30:
            stripe_by_day[dt] = stripe_by_day.get(dt, 0) + p["amount"]

    all_days_set = sorted(set(list(gumroad_by_day.keys()) + list(stripe_by_day.keys())))

    if all_days_set:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=all_days_set,
            y=[gumroad_by_day.get(d, 0) for d in all_days_set],
            name="Gumroad",
            marker_color="#FF4136",
            opacity=0.85,
        ))
        fig.add_trace(go.Bar(
            x=all_days_set,
            y=[stripe_by_day.get(d, 0) for d in all_days_set],
            name="Stripe",
            marker_color="#635BFF",
            opacity=0.85,
        ))
        fig.update_layout(
            barmode="stack",
            template="plotly_dark",
            height=280,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Inter"),
            paper_bgcolor="transparent",
            plot_bgcolor="transparent",
            xaxis=dict(showgrid=False, color="#555"),
            yaxis=dict(showgrid=True, gridcolor="#222", color="#555", tickprefix="£"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No paid revenue in the last 30 days.")

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── BY SOURCE ───────────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">Gumroad — Revenue by Product (All Time)</p>', unsafe_allow_html=True)
        product_revenue = {}
        for s in gumroad_paid:
            name = s.get("product_name", "Unknown")[:50]
            product_revenue[name] = product_revenue.get(name, 0) + gumroad_amount(s)

        if product_revenue:
            df_products = sorted(product_revenue.items(), key=lambda x: -x[1])
            fig_prod = go.Figure(go.Bar(
                x=[x[1] for x in df_products],
                y=[x[0] for x in df_products],
                orientation="h",
                marker_color="#FF4136",
                text=[f"£{x[1]:.2f}" for x in df_products],
                textposition="outside",
            ))
            fig_prod.update_layout(
                template="plotly_dark",
                height=max(200, len(df_products) * 48),
                margin=dict(l=0, r=80, t=10, b=0),
                font=dict(family="Inter"),
                paper_bgcolor="transparent",
                plot_bgcolor="transparent",
                xaxis=dict(showgrid=True, gridcolor="#222", color="#555", tickprefix="£"),
                yaxis=dict(color="#aaa"),
            )
            st.plotly_chart(fig_prod, use_container_width=True)
        else:
            st.info("No paid Gumroad sales yet.")

    with col_right:
        st.markdown('<p class="section-header">Revenue by Channel (All Time)</p>', unsafe_allow_html=True)

        fig_chan = go.Figure()
        fig_chan.add_trace(go.Pie(
            labels=["Gumroad", "Stripe"],
            values=[gumroad_total_revenue, stripe_total_revenue],
            marker_colors=["#FF4136", "#635BFF"],
            textinfo="label+value+percent",
            textposition="outside",
        ))
        fig_chan.update_layout(
            template="plotly_dark",
            height=280,
            margin=dict(l=0, r=0, t=20, b=0),
            font=dict(family="Inter"),
            paper_bgcolor="transparent",
            showlegend=False,
        )
        st.plotly_chart(fig_chan, use_container_width=True)

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── RECENT TRANSACTIONS ────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Recent Transactions</p>', unsafe_allow_html=True)

    transactions = []

    for s in gumroad_paid[:50]:
        dt = to_dt(s.get("created_at", ""))
        transactions.append({
            "date":   dt.strftime("%d %b %Y"),
            "source": "Gumroad",
            "product": s.get("product_name", "—")[:50],
            "amount":  f"£{gumroad_amount(s):.2f}",
            "customer": s.get("email", "—"),
        })

    for p in stripe_succeeded[:50]:
        dt = to_dt(p["created"])
        transactions.append({
            "date":    dt.strftime("%d %b %Y"),
            "source":  "Stripe",
            "product": p.get("description", "Review Responder")[:50],
            "amount":  f"£{p['amount']:.2f}",
            "customer": p.get("customer_email", "—"),
        })

    transactions.sort(key=lambda x: x["date"], reverse=True)
    transactions = transactions[:50]

    if transactions:
        # Header
        c1, c2, c3, c4, c5 = st.columns([1.2, 0.9, 3.2, 1.1, 2])
        with c1: st.markdown("**Date**")
        with c2: st.markdown("**Source**")
        with c3: st.markdown("**Product**")
        with c4: st.markdown("**Amount**")
        with c5: st.markdown("**Customer**")

        for row in transactions:
            src_color = {"Gumroad": "#FF4136", "Stripe": "#635BFF"}.get(row["source"], "#888")
            badge = f'<span style="background:{src_color};color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{row["source"]}</span>'

            c1, c2, c3, c4, c5 = st.columns([1.2, 0.9, 3.2, 1.1, 2])
            with c1: st.caption(row["date"])
            with c2: st.markdown(badge, unsafe_allow_html=True)
            with c3: st.caption(row["product"])
            with c4: st.markdown(f"**{row['amount']}**")
            with c5: st.caption(row["customer"][:30])
    else:
        st.info("No transactions yet. Revenue will appear here once you have sales.")

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── AFFILIATE LINKS ─────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Affiliate Links</p>', unsafe_allow_html=True)

    clicks = affiliate_data.get("clicks", {})
    conversions = affiliate_data.get("conversions", {})

    aff_cols = st.columns(3)
    for i, (key, info) in enumerate(AFFILIATE_LINKS.items()):
        col = aff_cols[i % 3]
        key_clicks = sum(v for k, v in clicks.items() if k.startswith(f"{key}:") or k == key)
        key_convs  = sum(v for k, v in conversions.items() if k.startswith(f"{key}:") or k == key)
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <p class="kpi-label">{info['name']}</p>
                <p style="font-size:13px;color:#c9a84c;margin:2px 0">{info['reward']}</p>
                <p style="font-size:20px;font-weight:700;color:#f5f5f0;margin:8px 0 0 0">{key_clicks} clicks</p>
                <p style="font-size:12px;color:#555;margin:2px 0 0 0">{key_convs} conversions</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption(
        "House of Knox Revenue Dashboard · "
        "Data: Gumroad API + Stripe API · "
        "Auto-refreshes every 5 minutes · "
        "Deployed on Streamlit Cloud"
    )


if __name__ == "__main__":
    main()
