import streamlit as st
from advisor import get_recommendation
from market import get_market_trends
from database import save_user, get_users
from chatbot import get_chatbot_response
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ✅ Page Configuration
st.set_page_config(
    page_title="SmartWealth | AI Investment Advisor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ✅ Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #2e7d32;
        color: white;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #1b5e20;
        border: 1px solid #4caf50;
    }
    [data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #30363d;
    }
    .reportview-container .main .block-container{
        padding-top: 2rem;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ---------------- #
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135706.png", width=100)
st.sidebar.title("SmartWealth")
st.sidebar.caption("Personalized AI Investment Advisor")


st.sidebar.markdown("---")
st.sidebar.subheader("👤 Your Profile")
age = st.sidebar.slider("Age", 18, 80, 25)
income = st.sidebar.number_input("Monthly Income/Savings (₹)", min_value=0, value=0, step=1000)
risk_appetite = st.sidebar.selectbox("Risk Appetite", ["Low", "Medium", "High"])
goal = st.sidebar.selectbox("Investment Goal", ["Wealth", "Retirement", "Education", "Safety"])


st.sidebar.markdown("---")
page = st.sidebar.selectbox("Navigation", ["🚀 Advisor", "📊 History", "🤖 Expert Chat"])

# ---------------- HELPER FUNCTIONS ---------------- #
def show_allocation_chart(risk):
    if risk == "Low":
        data = {"Bonds": 50, "Fixed Deposits": 20, "Gold": 20, "Safe Stocks": 10}
        colors = ["#2E7D32", "#FBC02D", "#0288D1", "#7B1FA2"] # Green, Yellow, Blue, Purple
    elif risk == "Medium":
        data = {"Mutual Funds": 40, "Blue-chip Stocks": 35, "Corporate Bonds": 15, "Gold": 10}
        colors = ["#1976D2", "#43A047", "#FB8C00", "#8E24AA"] # Blue, Green, Orange, Purple
    else:
        # High Risk
        data = {"Growth Stocks": 55, "Cryptocurrency": 25, "Emerging ETFs": 10, "Intl Tech": 10}
        colors = ["#E53935", "#5E35B1", "#FFB300", "#00897B"] # Red, Deep Purple, Amber, Teal
    
    df = pd.DataFrame(list(data.items()), columns=["Asset", "Percentage"])
    fig = px.pie(df, values="Percentage", names="Asset", hole=0.6, 
                 color_discrete_sequence=colors)

    
    fig.update_layout(
        showlegend=True, 
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(t=10, b=10, l=10, r=10), 
        height=350,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white")
    )
    return fig

# ---------------- PAGE 1: ADVISOR ---------------- #
if page == "🚀 Advisor":
    st.title("💰 Personalized AI Advisor")
    st.markdown(f"Helping you reach your **{goal}** goals.")

    col1, col2 = st.columns([1.5, 1])

    with col1:
        if st.button("🚀 Generate AI Recommendation"):
            with st.spinner("SmartWealth AI is analyzing your profile..."):
                rec = get_recommendation(age, income, goal)
                
                # Save to database
                save_user(age, income, goal, rec['risk'], rec['title'], rec['strategy'])
                
                st.markdown(f"### 🛡️ {rec['title']}")
                st.info(f"**Calculated Risk Profile:** {rec['risk']}")
                st.success(rec['strategy'])
                
                st.markdown("---")
                st.subheader("📌 Optimized Asset Allocation")
                fig = show_allocation_chart(rec['risk'])
                st.plotly_chart(fig, theme="streamlit")


        else:
            st.info("Adjust your profile in the sidebar and click the button above to get a personalized strategy.")

    with col2:
        st.subheader("📈 Live Market Pulse")
        # 🔥 CACHED for performance (refreshes every 10 minutes)
        @st.cache_data(ttl=600)
        def fetch_trends():
            return get_market_trends()

        with st.spinner("Updating market pulse..."):
            trends = fetch_trends()
            for stock, info in trends.items():

                prices = info["prices"]
                sentiment = info["sentiment"]
                
                # Sentiment Color Logic
                if sentiment == "Positive":
                    sentiment_color = "green"
                    sentiment_emoji = "🔼"
                elif sentiment == "Negative":
                    sentiment_color = "red"
                    sentiment_emoji = "🔽"
                else:
                    sentiment_color = "gray"
                    sentiment_emoji = "➖"
                
                with st.container():
                    st.markdown(f"**{stock}** | Sentiment: <span style='color:{sentiment_color}'>{sentiment} {sentiment_emoji}</span>", unsafe_allow_html=True)
                    st.line_chart(prices, height=120)
                    st.divider()


# ---------------- PAGE 2: HISTORY ---------------- #
elif page == "📊 History":
    st.title("📊 Your Investment History")
    
    users = get_users()
    if users:
        df = pd.DataFrame(users, columns=["ID", "Age", "Income", "Goal", "Risk", "Title", "Strategy", "Timestamp"])
        # Format timestamp
        df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(df.style.set_properties(**{'background-color': '#161b22', 'color': 'white'}), use_container_width=True)
        
        # Simple stats
        st.subheader("Historical Goals Distribution")
        goal_counts = df['Goal'].value_counts().reset_index()
        fig = px.bar(goal_counts, x='Goal', y='count', color='Goal', title="Goals Tracked")
        st.plotly_chart(fig)
    else:
        st.warning("No history found. Go to the Advisor page to get your first recommendation!")

# ---------------- PAGE 3: CHATBOT ---------------- #
elif page == "🤖 Expert Chat":
    st.title("🤖 AI Financial Assistant")
    st.markdown("Ask me anything about stocks, risk, or general financial planning.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("How should I diversify my portfolio?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = get_chatbot_response(prompt)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})