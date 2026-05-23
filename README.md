# SmartWealth | Personalized AI-Based Investment Advisor 📈💰

SmartWealth is a sophisticated AI-powered financial advisory platform designed to recommend personalized investment strategies based on user profiles, goals, and real-time market trends. 

Unlike traditional advisors, SmartWealth combines **Symbolic AI (Rule-based Expert Systems)** with **Data-driven NLP (Natural Language Processing)** to provide a 360-degree investment perspective.

---

## 🌟 Key Features

- **🧠 Logic-Driven Expert System**: Uses **Prolog** to reason through user data (Age, Income, Goals) and categorize risk profiles with high precision.
- **📰 NLP Sentiment Analysis**: Analyzes real-time news headlines for stocks using **TextBlob** to determine market sentiment (Bullish/Bearish).
- **📈 Real-time Market Pulse**: Integrates with the **yfinance API** to display live stock charts and price trends.
- **🎨 Premium UI/UX**: A modern, dark-themed dashboard built with **Streamlit** featuring interactive **Plotly** charts.
- **🤖 Intelligent Chatbot**: A cross-platform financial assistant for quick queries about diversification and risk management.
- **📊 Historical Tracking**: Persistent data storage with **SQLite** to monitor your previous advisory reports.

---

## 🛠️ Technology Stack

- **Python**: Core application logic.
- **Prolog (SWI-Prolog & PySwip)**: The symbolic AI logic engine.
- **Streamlit**: The responsive web interface.
- **yfinance**: Real-time financial data fetching.
- **TextBlob**: Natural Language Processing for sentiment detection.
- **SQLite**: Reliable local database storage.
- **Plotly**: Advanced data visualization.

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.10+**
2. **SWI-Prolog**: You MUST have SWI-Prolog installed and added to your system PATH for the Expert System to function. [Download here](https://www.swi-prolog.org/download/stable).

### Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application**:
   ```bash
   streamlit run app.py
   ```

---

## 📁 Project Structure

- `app.py`: The main UI and application controller.
- `rules.pl`: The Prolog codebase containing the AI logic rules.
- `advisor.py`: The bridge between the Python UI and Prolog brain.
- `market.py`: Handles real-time API data fetching and NLP sentiment.
- `database.py`: Manages SQLite persistence and user history.
- `chatbot.py`: Logic for the AI financial assistant.

---

## 🚀 Team Project
**Personalized AI-Based Investment Advisor** 

*Developed for the AI Final Submission.*

