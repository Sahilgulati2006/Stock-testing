# Stock Analysis and Portfolio Management System

A comprehensive stock market analysis and portfolio management system that combines fundamental analysis, sentiment analysis, and AI-powered insights to help investors make informed decisions.

## Features

- **Stock Analysis**: Detailed analysis of stocks including historical data, technical indicators, and fundamental metrics
- **Sentiment Analysis**: Integration of social media and news sentiment analysis for market insights
- **Portfolio Management**: Tools for tracking and managing investment portfolios
- **AI-Powered Insights**: Warren Buffett-inspired AI analysis for stock recommendations
- **Market Sentiment**: Real-time market sentiment tracking and analysis
- **Web Search Integration**: Enhanced research capabilities with web search integration

## Tech Stack

- **Backend**: Flask (Python)
- **Data Processing**: Pandas, NumPy
- **Machine Learning**: Scikit-learn, PyTorch, Transformers
- **Data Visualization**: Matplotlib, Seaborn, Plotly
- **APIs**: Polygon.io, Twitter (via Tweepy), Reddit (via Praw)
- **Deployment**: Gunicorn

## Prerequisites

- Python 3.8+
- Polygon.io API key
- Twitter API credentials (for sentiment analysis)
- Reddit API credentials (for sentiment analysis)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd [repository-name]
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your API keys and credentials

## Configuration

Create a `.env` file in the root directory with the following variables:
```
POLYGON_API_KEY=your_api_key_here
```

## Running the Application

1. Start the Flask application:
```bash
python run.py
```

2. Access the application at `http://localhost:8000`

## Project Structure

```
├── app/
│   ├── templates/          # HTML templates
│   ├── __init__.py        # Application factory
│   ├── config.py          # Configuration settings
│   ├── routes.py          # Main application routes
│   ├── stock_service.py   # Stock analysis services
│   ├── sentiment_service.py # Sentiment analysis
│   ├── portfolio_service.py # Portfolio management
│   └── warren_buffett_ai.py # AI analysis module
├── data/
│   └── portfolio.json     # Portfolio data storage
├── requirements.txt       # Python dependencies
└── run.py                # Application entry point
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Polygon.io for financial data
- Twitter and Reddit APIs for sentiment analysis
- Various open-source libraries and frameworks
