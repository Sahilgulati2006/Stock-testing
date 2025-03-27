from flask import Blueprint, render_template, request, jsonify
from app.stock_service import StockService
from app.sentiment_service import SentimentService
from datetime import date, timedelta
import yfinance as yf

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/analyze', methods=['POST'])
def analyze():
    ticker = request.form.get('ticker', '').upper()
    
    # Get stock data
    stock_data = StockService.get_stock_data(ticker)
    stock_data = StockService.calculate_technical_indicators(stock_data)
    fib_levels = StockService.calculate_fibonacci_levels(stock_data)
    
    # Get news and fundamentals
    news = StockService.get_stock_news(ticker)
    fundamentals = StockService.get_fundamentals(ticker)
    
    return render_template('analysis.html', 
                         ticker=ticker,
                         stock_data=stock_data.tail(50).to_dict('records'),
                         fib_levels=fib_levels,
                         news=news,
                         fundamentals=fundamentals)

@main.route('/sentiment', methods=['GET', 'POST'])
def sentiment_analysis():
    if request.method == 'POST':
        subreddit = request.form.get('subreddit', 'wallstreetbets')
        sentiment_service = SentimentService()
        analysis = sentiment_service.analyze_subreddit(subreddit)
        return render_template('sentiment.html', analysis=analysis)
    
    return render_template('sentiment.html')

@main.route('/portfolio', methods=['GET', 'POST'])
def portfolio_analysis():
    if request.method == 'POST':
        # Process portfolio form
        pass
    return render_template('portfolio.html')