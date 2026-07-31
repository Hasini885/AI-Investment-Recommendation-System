"""SmartWealth - Streamlit front end.

Notes on things that were previously wrong and are now load-bearing:

  * Risk appetite is passed into the advisor.  It used to be collected and
    silently discarded.
  * The donut chart and the strategy sentence both render from
    ``recommendation["allocation"]`` - one source, so they cannot disagree.
  * The recommendation lives in ``st.session_state``, so it survives the
    script re-run that Streamlit performs on every widget interaction.
  * Market sentiment is fetched before inference and fed into it.
"""

import uuid

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from advisor import GOALS, TOLERANCES, InvalidProfile, get_recommendation
from chatbot import get_chatbot_response
from database import get_recommendations, latest_recommendation, save_recommendation
from market import aggregate_sentiment, get_market_trends

st.set_page_config(
    page_title="SmartWealth | AI Investment Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Visual tokens.
#
# Categorical slots are the validated dark-surface palette, applied in fixed
# slot order (blue, orange, aqua, yellow, magenta).  Allocations are authored
# largest-first and never re-sorted at render time, so a given asset always
# keeps its colour within a portfolio.  The slot order also keeps orange and
# yellow off adjacent ring segments - that is the one pair in this palette
# that is hard to separate under deuteranopia.
# ---------------------------------------------------------------------------
SURFACE = "#0e1117"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]
INK_PRIMARY = "#ffffff"
INK_MUTED = "#898781"
GRIDLINE = "#2c2c2a"

SENTIMENT_STYLE = {
    "Positive": ("#0ca30c", "▲"),
    "Negative": ("#d03b3b", "▼"),
    "Neutral": (INK_MUTED, "■"),
    "Unavailable": (INK_MUTED, "–"),
}

st.markdown(
    f"""
    <style>
    .main {{ background-color: {SURFACE}; }}
    .stButton>button {{
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #2e7d32;
        color: white;
        font-weight: bold;
        transition: 0.3s;
    }}
    .stButton>button:hover {{
        background-color: #1b5e20;
        border: 1px solid #4caf50;
    }}
    [data-testid="stSidebar"] {{
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }}
    .disclaimer {{
        font-size: 0.82rem;
        color: {INK_MUTED};
        border-left: 3px solid #30363d;
        padding: 0.4rem 0 0.4rem 0.8rem;
        margin-top: 1.2rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

DISCLAIMER = (
    "**Educational use only.** SmartWealth is an academic project, not investment advice. "
    "It is not produced by a SEBI-registered adviser, does not account for your full "
    "financial position, tax situation or liabilities, and past market performance does not "
    "predict future returns. Consult a qualified financial adviser before investing."
)

# One id per browser session, so History shows *your* history rather than
# every previous visitor's.
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


@st.cache_data(ttl=600, show_spinner=False)
def fetch_trends():
    """Live market data, refreshed at most every 10 minutes."""
    return get_market_trends()


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def allocation_donut(allocation):
    """Part-to-whole donut for a portfolio allocation (always <= 6 segments).

    Segments carry direct percentage labels and a 2px surface gap, which is
    the secondary encoding the palette's CVD margin requires - identity never
    rests on hue alone.  The table beside it is the WCAG-clean twin.
    """
    labels = list(allocation.keys())
    values = list(allocation.values())

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            sort=False,
            direction="clockwise",
            marker=dict(
                colors=SERIES[: len(labels)],
                line=dict(color=SURFACE, width=2),
            ),
            texttemplate="%{value}%",
            textposition="inside",
            insidetextorientation="horizontal",
            textfont=dict(color=INK_PRIMARY, size=13),
            hovertemplate="%{label}<br>%{value}% of portfolio<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5,
                    font=dict(color=INK_MUTED, size=12)),
        margin=dict(t=10, b=10, l=10, r=10),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif'),
    )
    return fig


def price_sparkline(dates, prices):
    """Single-series price line: 2px mark, hairline grid, no legend."""
    fig = go.Figure(
        go.Scatter(
            x=dates,
            y=prices,
            mode="lines",
            line=dict(color=SERIES[0], width=2),
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=150,
        margin=dict(t=6, b=6, l=6, r=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hovermode="x unified",
        xaxis=dict(showgrid=False, color=INK_MUTED, tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor=GRIDLINE, gridwidth=1,
                   color=INK_MUTED, tickfont=dict(size=10)),
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif'),
    )
    return fig


def goal_bar(counts):
    """Nominal categories, one measure -> a single series colour, not a ramp."""
    fig = go.Figure(
        go.Bar(
            x=counts["Goal"],
            y=counts["Count"],
            marker=dict(color=SERIES[0]),
            hovertemplate="%{x}<br>%{y} recommendation(s)<extra></extra>",
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis=dict(showgrid=False, color=INK_MUTED),
        yaxis=dict(showgrid=True, gridcolor=GRIDLINE, gridwidth=1,
                   color=INK_MUTED, dtick=1),
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif'),
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("SmartWealth")
st.sidebar.caption("Personalised Investment Advisor")
st.sidebar.markdown("---")

st.sidebar.subheader("👤 Your Profile")
age = st.sidebar.slider("Age", 18, 80, 30)
income = st.sidebar.number_input(
    "Monthly investable income (₹)",
    min_value=0,
    max_value=10_000_000,
    value=40_000,
    step=5_000,
    help="Income you can realistically commit each month after expenses and EMIs.",
)
risk_appetite = st.sidebar.selectbox(
    "Risk appetite",
    [t.capitalize() for t in TOLERANCES],
    index=1,
    help="Your comfort with volatility. The advisor never exceeds this, even if "
         "your profile could support more risk.",
)
goal = st.sidebar.selectbox("Investment goal", [g.capitalize() for g in GOALS])

st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["🚀 Advisor", "📊 History", "💬 Expert Chat"])

# ---------------------------------------------------------------------------
# Advisor
# ---------------------------------------------------------------------------
if page == "🚀 Advisor":
    st.title("💰 Personalised Investment Advisor")
    st.markdown(f"Building a strategy for your **{goal.lower()}** goal.")

    col1, col2 = st.columns([1.6, 1])

    with col2:
        st.subheader("📈 Live Market Pulse")
        with st.spinner("Updating market pulse…"):
            trends = fetch_trends()
        signal, signal_summary = aggregate_sentiment(trends)

        st.caption(f"Overall news sentiment: **{signal}** — {signal_summary}")

        for symbol, info in trends.items():
            colour, glyph = SENTIMENT_STYLE.get(info["sentiment"], SENTIMENT_STYLE["Neutral"])
            change = info.get("change_pct")
            change_txt = f" · {change:+.2f}% (5d)" if change is not None else ""

            st.markdown(
                f"**{info['name']}**{change_txt} &nbsp;|&nbsp; "
                f"<span style='color:{colour}'>{glyph} {info['sentiment']}</span>",
                unsafe_allow_html=True,
            )
            if info["error"]:
                st.caption(f"⚠️ {info['error']}")
            elif info["prices"]:
                st.plotly_chart(
                    price_sparkline(info["dates"], info["prices"]),
                    use_container_width=True,
                    theme=None,
                    key=f"spark_{symbol}",
                )
            if info["detail"]:
                st.caption(info["detail"])
            st.divider()

    with col1:
        if st.button("🚀 Generate Recommendation"):
            try:
                rec = get_recommendation(age, income, risk_appetite, goal, signal)
            except InvalidProfile as exc:
                st.error(str(exc))
            else:
                # Persist across the re-runs Streamlit triggers on every
                # widget interaction, so the result does not vanish.
                st.session_state.recommendation = rec
                st.session_state.profile = {
                    "age": age, "income": income,
                    "risk_appetite": risk_appetite.lower(), "goal": goal.lower(),
                }
                save_recommendation(
                    st.session_state.session_id, age, income,
                    risk_appetite.lower(), goal.lower(), rec,
                )

        rec = st.session_state.get("recommendation")
        if rec is None:
            st.info(
                "Set your profile in the sidebar and generate a recommendation. "
                "The advisor weighs what you can afford to risk against what you "
                "are comfortable with, and takes the lower of the two."
            )
        else:
            st.markdown(f"### 🛡️ {rec['title']}")
            badge = "SWI-Prolog expert system" if rec["engine"] == "prolog" else "Python rule engine"
            st.caption(f"Risk profile: **{rec['risk_label']}** · inferred by the {badge}")

            st.success(rec["strategy"])

            st.subheader("🧭 Why this recommendation")
            for reason in rec["reasons"]:
                st.markdown(f"- {reason}")

            st.subheader("📌 Asset allocation")
            chart_col, table_col = st.columns([1.3, 1])
            with chart_col:
                st.plotly_chart(
                    allocation_donut(rec["allocation"]),
                    use_container_width=True,
                    theme=None,
                    key="allocation_donut",
                )
            with table_col:
                monthly = st.session_state.profile["income"]
                table = pd.DataFrame(
                    [
                        {
                            "Asset": asset,
                            "Share": f"{pct}%",
                            "Monthly (₹)": f"{round(monthly * pct / 100):,}",
                        }
                        for asset, pct in rec["allocation"].items()
                    ]
                )
                st.dataframe(table, hide_index=True, use_container_width=True)

    st.markdown(f"<div class='disclaimer'>{DISCLAIMER}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
elif page == "📊 History":
    st.title("📊 Recommendation History")

    show_all = st.checkbox(
        "Show recommendations from all sessions", value=False,
        help="By default this page shows only recommendations generated in your "
             "current browser session.",
    )
    rows = get_recommendations(None if show_all else st.session_state.session_id)

    if not rows:
        scope = "in this database" if show_all else "in this session"
        st.warning(f"No recommendations {scope} yet. Generate one on the Advisor page.")
    else:
        df = pd.DataFrame(rows)
        display = pd.DataFrame({
            "When": pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M"),
            "Age": df["age"],
            "Income (₹)": df["income"],
            "Appetite": df["risk_appetite"].fillna("—").str.capitalize(),
            "Goal": df["goal"].fillna("—").str.capitalize(),
            "Market": df["market_sentiment"].fillna("—").str.capitalize(),
            "Risk": df["risk"].fillna("—").str.capitalize(),
            "Strategy": df["strategy_title"],
            "Engine": df["engine"].fillna("—"),
        })
        st.dataframe(display, hide_index=True, use_container_width=True)

        st.download_button(
            "⬇️ Download history as CSV",
            display.to_csv(index=False).encode("utf-8"),
            file_name="smartwealth_history.csv",
            mime="text/csv",
        )

        st.subheader("Goals recorded")
        # groupby().size() rather than value_counts().reset_index(): the latter
        # names its output column differently across pandas versions.
        counts = display.groupby("Goal", as_index=False).size()
        counts = counts.rename(columns={"size": "Count"})
        st.plotly_chart(goal_bar(counts), use_container_width=True, theme=None, key="goal_bar")

    st.markdown(f"<div class='disclaimer'>{DISCLAIMER}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
elif page == "💬 Expert Chat":
    st.title("💬 Financial Assistant")
    st.caption(
        "A rule-based assistant covering investing fundamentals. It can also explain "
        "the recommendation you generated — try *“what is my profile?”* or *“why?”*."
    )

    # Give the assistant the user's own recommendation, falling back to the
    # last one stored for this session.
    context = st.session_state.get("recommendation")
    if context is None:
        stored = latest_recommendation(st.session_state.session_id)
        if stored:
            context = {
                "risk_label": (stored["risk"] or "").capitalize(),
                "title": stored["strategy_title"],
                "strategy": stored["strategy_details"],
                "reasons": [r for r in (stored["reasoning"] or "").split(" | ") if r],
            }

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("How should I diversify my portfolio?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        response = get_chatbot_response(prompt, context)
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

    st.markdown(f"<div class='disclaimer'>{DISCLAIMER}</div>", unsafe_allow_html=True)
