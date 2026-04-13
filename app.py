"""
House of Knox — Revenue Dashboard
One view of all income streams: Gumroad, Stripe, Affiliate.
Deployed on Streamlit Cloud.
"""

import streamlit as st
import sqlite3
import json
import requests
import plotly.express as px
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

# ─── CREDENTIALS ───────────────────────────────────────────────────────────────
WORKSPACE = Path(os.environ.get("WORKSPACE", r"C:\Users\cknox\.openclaw\workspace"))

GUMROAD_TOKEN = os.environ.get("GUMROAD_TOKEN", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")

# ─── STYLING ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stMetric { background: #111; border: 1px solid #222; border-radius: 8px; padding: 16px 24px; }
    .stMetric label { color: #888 !important; font-size: 13px !important; text-transform: uppercase; letter-spacing: 0.06em; }
    .stMetric [data-testid="stMetricValue"] { color: #f5f5f0 !important; font-size: 28px !important; font-weight: 700 !important; }
    .source-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .gumroad { background: #FF4136; color: white; }
    .stripe { background: #635BFF; color: white; }
    .affiliate { background: #00D4AA; color: #000; }
    .section-header { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #c9a84c; margin-bottom: 8px; font-weight: 600; }
    .kpi-card { background: #111; border: 1px solid #222; border-radius: 8px; padding: 20px 24px; }
    .kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #666; margin: 0 0 4px 0; }
    .kpi-value { font-size: 32px; font-weight: 700; color: #f5f5f0; margin: 0; }
    .kpi-sub { font-size: 12px; color: #555; margin: 4px 0 0 0; }
    .divider { border: none; border-top: 1px solid #222; margin: 24px 0; }
</style>
""", unsafe_allow_html=True)

# ─── DATA: GUMROAD ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_gumroad_data():
    """Pull sales from local SQLite DB (populated by gumroad_monitor.py)"""
    db_path = WORKSPACE / "gumroad_sales.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, created_at, product_name, price, currency_symbol,
               paid, country, email, referrer, captured_at
        FROM gumroad_sales
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gumroad_realtime():
    """Poll Gumroad API for latest sales"""
    if not GUMROAD_TOKEN:
        return []
    try:
        headers = {"Authorization": f"Bearer {GUMROAD_TOKEN}"}
        r = requests.get(
            "https://api.gumroad.com/v2/sales",
            headers=headers,
            params={"per_page": 20},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("sales", [])
        return data
    except Exception as e:
        return []


# ─── DATA: STRIPE ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stripe_data():
    """Pull payment intents from Stripe API"""
    if not STRIPE_SECRET_KEY:
        return []

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY

        # Get payment intents from last 90 days
        since = datetime.now(timezone.utc) - timedelta(days=90)
        pis = stripe.PaymentIntent.list(
            created={"gte": int(since.timestamp())},
            limit=100,
        )

        results = []
        for pi in pis.data:
            results.append({
                "id": pi.id,
                "amount": pi.amount / 100,  # convert from cents
                "currency": pi.currency.upper(),
                "status": pi.status,
                "created": datetime.fromtimestamp(pi.created, tz=timezone.utc).isoformat(),
                "description": pi.description or "Review Responder",
                "customer_email": pi.receipt_email or "",
            })
        return results
    except Exception as e:
        return []


# ─── DATA: AFFILIATE ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_affiliate_data():
    """Load affiliate tracker data"""
    tracker_path = WORKSPACE / "review_responder" / "affiliate_tracker.json"
    if not tracker_path.exists():
        return {"clicks": {}, "conversions": {}}

    with open(tracker_path) as f:
        return json.load(f)


AFFILIATE_LINKS = {
    "claude": {"name": "Claude", "url": "https://claude.ai/invite/tqK3NqJxHN6gQZi2K", "reward": "$50/user"},
    "anthropic": {"name": "Anthropic API", "url": "https://www.anthropic.com/api", "reward": "20% for 3mo"},
    "openai": {"name": "OpenAI API", "url": "https://platform.openai.com", "reward": "30d credits"},
    "stripe": {"name": "Stripe", "url": "https://stripe.com/referrals", "reward": "$50/sale"},
    "beehiiv": {"name": "Beehiiv", "url": "https://www.beehiiv.com", "reward": "$10/referral"},
    "perplexity": {"name": "Perplexity", "url": "https://perplexity.ai/pro", "reward": "$10 credit"},
    "render": {"name": "Render", "url": "https://render.com", "reward": "$100/paying customer"},
    "semrush": {"name": "SEMrush", "url": "https://semrush.com", "reward": "200 EUR + 30%"},
}


# ─── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    st.markdown("## 💰 House of Knox — Revenue Dashboard")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y, %H:%M')} BST")

    # ── KPI ROW ─────────────────────────────────────────────────────────────────
    gumroad_sales = get_gumroad_data()
    stripe_payments = get_stripe_data()
    affiliate_data = get_affiliate_data()

    # Calculate KPIs
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Gumroad: paid sales this month (price is in cents)
    gumroad_month = [
        s for s in gumroad_sales
        if s.get("paid") and datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) >= this_month_start
    ]
    gumroad_month_revenue = sum(s["price"] for s in gumroad_month) / 100
    gumroad_total_revenue = sum(s["price"] for s in gumroad_sales if s.get("paid")) / 100
    gumroad_total_count = len([s for s in gumroad_sales if s.get("paid")])

    # Stripe: completed payments this month
    stripe_month = [
        p for p in stripe_payments
        if p["status"] == "succeeded" and
        datetime.fromisoformat(p["created"].replace("Z", "+00:00")) >= this_month_start
    ]
    stripe_month_revenue = sum(p["amount"] for p in stripe_month)
    stripe_total_revenue = sum(p["amount"] for p in stripe_payments if p["status"] == "succeeded")

    # Affiliate clicks
    affiliate_clicks = sum(affiliate_data.get("clicks", {}).values())

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown('<p class="kpi-label">Gumroad This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{gumroad_month_revenue:,.2f}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{len(gumroad_month)} sale{"s" if len(gumroad_month) != 1 else ""} · £{(gumroad_month_revenue/len(gumroad_month) if gumroad_month else 0):.2f} avg</p>', unsafe_allow_html=True)

    with col2:
        st.markdown('<p class="kpi-label">Stripe This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{stripe_month_revenue:,.2f}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{len(stripe_month)} payment{"s" if len(stripe_month) != 1 else ""}</p>', unsafe_allow_html=True)

    with col3:
        combined_month = gumroad_month_revenue + stripe_month_revenue
        st.markdown('<p class="kpi-label">Combined This Month</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">£{combined_month:,.2f}</p>', unsafe_allow_html=True)
        st.markdown('<p class="kpi-sub">Gumroad + Stripe</p>', unsafe_allow_html=True)

    with col4:
        affiliate_conversions = sum(affiliate_data.get("conversions", {}).values())
        st.markdown('<p class="kpi-label">Affiliate Clicks</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-value">{affiliate_clicks}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="kpi-sub">{affiliate_conversions} conversions (untracked)</p>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── REVENUE OVER TIME ───────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Revenue Over Time — Last 30 Days</p>', unsafe_allow_html=True)

    # Build daily aggregation for Gumroad
    gumroad_by_day = {}
    for s in gumroad_sales:
        if not s.get("paid"):
            continue
        dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")).date()
        gumroad_by_day[dt] = gumroad_by_day.get(dt, 0) + s["price"] / 100

    stripe_by_day = {}
    for p in stripe_payments:
        if p["status"] != "succeeded":
            continue
        dt = datetime.fromisoformat(p["created"].replace("Z", "+00:00")).date()
        stripe_by_day[dt] = stripe_by_day.get(dt, 0) + p["amount"]

    # Merge into one timeline
    all_days = sorted(set(list(gumroad_by_day.keys()) + list(stripe_by_day.keys())))
    last_30_days = [d for d in all_days if d >= now.date() - timedelta(days=30)]

    if last_30_days:
        dates = last_30_days
        gumroad_vals = [gumroad_by_day.get(d, 0) for d in dates]
        stripe_vals = [stripe_by_day.get(d, 0) for d in dates]
        combined_vals = [g + s for g, s in zip(gumroad_vals, stripe_vals)]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates, y=gumroad_vals,
            name="Gumroad", marker_color="#FF4136", opacity=0.85,
        ))
        fig.add_trace(go.Bar(
            x=dates, y=stripe_vals,
            name="Stripe", marker_color="#635BFF", opacity=0.85,
        ))
        fig.update_layout(
            barmode="stack",
            template="plotly_dark",
            height=300,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="Inter"),
            paper_bgcolor="transparent",
            plot_bgcolor="transparent",
            xaxis=dict(showgrid=False, color="#555"),
            yaxis=dict(showgrid=True, gridcolor="#222", color="#555"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No paid revenue in the last 30 days. Add payment data to see the chart.")

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── BY SOURCE ────────────────────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<p class="section-header">Revenue by Product — All Time</p>', unsafe_allow_html=True)

        # Aggregate by product
        product_revenue = {}
        for s in gumroad_sales:
            if not s.get("paid"):
                continue
            name = s.get("product_name", "Unknown")
            product_revenue[name] = product_revenue.get(name, 0) + s["price"] / 100

        if product_revenue:
            df_products = sorted(product_revenue.items(), key=lambda x: -x[1])
            fig_prod = go.Figure(go.Bar(
                x=[x[1] for x in df_products],
                y=[x[0][:40] for x in df_products],
                orientation="h",
                marker_color="#FF4136",
                text=[f"£{x[1]:.2f}" for x in df_products],
                textposition="outside",
            ))
            fig_prod.update_layout(
                template="plotly_dark",
                height=max(200, len(df_products) * 50),
                margin=dict(l=0, r=60, t=10, b=0),
                font=dict(family="Inter"),
                paper_bgcolor="transparent",
                plot_bgcolor="transparent",
                xaxis=dict(showgrid=True, gridcolor="#222", color="#555", title="GBP"),
                yaxis=dict(color="#aaa"),
            )
            st.plotly_chart(fig_prod, use_container_width=True)
        else:
            st.info("No paid Gumroad sales yet.")

    with col_right:
        st.markdown('<p class="section-header">Revenue by Channel — All Time</p>', unsafe_allow_html=True)

        gumroad_total = sum(s["price"] / 100 for s in gumroad_sales if s.get("paid"))
        stripe_total = sum(p["amount"] for p in stripe_payments if p["status"] == "succeeded")

        fig_chan = go.Figure()
        channels = ["Gumroad", "Stripe"]
        revenues = [gumroad_total, stripe_total]
        colors = ["#FF4136", "#635BFF"]
        fig_chan.add_trace(go.Pie(
            labels=channels,
            values=revenues,
            marker_colors=colors,
            textinfo="label+value+percent",
            textposition="outside",
        ))
        fig_chan.update_layout(
            template="plotly_dark",
            height=300,
            margin=dict(l=0, r=0, t=20, b=0),
            font=dict(family="Inter"),
            paper_bgcolor="transparent",
            showlegend=False,
        )
        st.plotly_chart(fig_chan, use_container_width=True)

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── RECENT TRANSACTIONS ─────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Recent Transactions</p>', unsafe_allow_html=True)

    # Combine Gumroad + Stripe
    transactions = []

    for s in gumroad_sales[:50]:
        if not s.get("paid"):
            continue
        dt = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
        transactions.append({
            "date": dt.strftime("%d %b %Y"),
            "source": "Gumroad",
            "product": s.get("product_name", "Unknown")[:50],
            "amount": f"£{s['price'] / 100:.2f}",
            "currency": s.get("currency_symbol", "£"),
            "customer": s.get("email", "—"),
            "country": s.get("country", "—"),
        })

    for p in stripe_payments[:50]:
        if p["status"] != "succeeded":
            continue
        dt = datetime.fromisoformat(p["created"].replace("Z", "+00:00"))
        transactions.append({
            "date": dt.strftime("%d %b %Y"),
            "source": "Stripe",
            "product": p.get("description", "Review Responder")[:50],
            "amount": f"£{p['amount']:.2f}",
            "currency": p.get("currency", "GBP"),
            "customer": p.get("customer_email", "—"),
            "country": "—",
        })

    # Sort by date descending
    transactions.sort(key=lambda x: x["date"], reverse=True)
    transactions = transactions[:50]

    if transactions:
        import pandas as pd
        df_tx = pd.DataFrame(transactions)

        # Color source badges
        def source_badge(src):
            color = {"Gumroad": "#FF4136", "Stripe": "#635BFF"}.get(src, "#888")
            return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{src}</span>'

        df_tx["source_badge"] = df_tx["source"].apply(source_badge)

        col_d, col_s, col_p, col_a, col_c = st.columns([1.2, 1, 3, 1, 2])
        with col_d: st.markdown("**Date**")
        with col_s: st.markdown("**Source**")
        with col_p: st.markdown("**Product**")
        with col_a: st.markdown("**Amount**")
        with col_c: st.markdown("**Customer**")

        for _, row in df_tx.iterrows():
            cols = st.columns([1.2, 1, 3, 1, 2])
            with cols[0]: st.caption(row["date"])
            with cols[1]: st.markdown(row["source_badge"], unsafe_allow_html=True)
            with cols[2]: st.caption(row["product"])
            with cols[3]: st.markdown(f"**{row['amount']}**")
            with cols[4]: st.caption(row["customer"][:30])

    else:
        st.info("No transactions yet. Revenue will appear here once you have sales.")

    st.markdown("<hr class='divider'/>", unsafe_allow_html=True)

    # ── AFFILIATE LINKS ──────────────────────────────────────────────────────────
    st.markdown('<p class="section-header">Affiliate Links</p>', unsafe_allow_html=True)

    clicks = affiliate_data.get("clicks", {})
    conversions = affiliate_data.get("conversions", {})

    aff_cols = st.columns(3)
    for i, (key, info) in enumerate(AFFILIATE_LINKS.items()):
        col = aff_cols[i % 3]
        key_clicks = sum(v for k, v in clicks.items() if k.startswith(f"{key}:") or k == key)
        key_convs = sum(v for k, v in conversions.items() if k.startswith(f"{key}:") or k == key)
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <p class="kpi-label">{info['name']}</p>
                <p style="font-size:13px;color:#c9a84c;margin:2px 0">{info['reward']}</p>
                <p style="font-size:20px;font-weight:700;color:#f5f5f0;margin:8px 0 0 0">{key_clicks} clicks</p>
                <p style="font-size:12px;color:#555;margin:2px 0 0 0">{key_convs} conversions</p>
                <p style="font-size:11px;color:#333;margin:4px 0 0 0;word-break:break-all">{info['url'][:60]}...</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("House of Knox Revenue Dashboard · Data: Gumroad API + Stripe API · Refreshes every 5 minutes on Streamlit Cloud")


if __name__ == "__main__":
    main()
