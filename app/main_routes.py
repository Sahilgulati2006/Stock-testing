from flask import Blueprint, render_template, request, jsonify
from app.stock_service import StockService
from app.sentiment_service import SentimentService
from datetime import date, timedelta
import yfinance as yf
import pandas as pd

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/analyze', methods=['POST'])
def analyze():
    ticker = request.form.get('ticker', '').upper()
    print(f"\nStarting analysis for {ticker}")
    
    try:
        # Get stock data and calculate indicators
        print(f"Fetching stock data for {ticker}")
        stock_data = StockService.get_stock_data(ticker)
        print(f"Calculating technical indicators for {ticker}")
        stock_data = StockService.calculate_technical_indicators(stock_data)
        
        # Analyze trends
        print("Analyzing trends")
        trend_analysis = StockService.analyze_trends(stock_data)
        if trend_analysis:
            print(f"Current trend: {trend_analysis.get('current_trend')}")
        
        # Calculate Fibonacci levels
        print("Calculating Fibonacci levels")
        fib_levels = StockService.calculate_fibonacci_levels(stock_data)
        
        # Get news and fundamentals
        print("Fetching news and fundamentals")
        news = StockService.get_stock_news(ticker)
        fundamentals = StockService.get_fundamentals(ticker)
        
        # Convert DataFrame to records for chart
        print("Converting data for chart display")
        stock_records = []
        for idx, row in stock_data.iterrows():
            try:
                record = {
                    'Date': idx.strftime('%Y-%m-%d'),
                    'Close': float(row['Close']),
                    'EMA_50': float(row['EMA_50']),
                    'EMA_100': float(row['EMA_100']),
                    'RSI': float(row['RSI'])
                }
                stock_records.append(record)
            except Exception as e:
                print(f"Error processing row for {ticker} at {idx}: {str(e)}")
                continue
        
        print(f"Processed {len(stock_records)} records for chart")
        if not stock_records:
            raise ValueError(f"No valid stock data could be processed for {ticker}")
        
        print(f"Analysis completed successfully for {ticker}")
        return render_template('analysis.html', 
                             ticker=ticker,
                             stock_data=stock_records,
                             trend_analysis=trend_analysis,
                             fib_levels=fib_levels,
                             news=news,
                             fundamentals=fundamentals)
                             
    except Exception as e:
        error_msg = f"Error analyzing {ticker}: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return render_template('analysis.html',
                             ticker=ticker,
                             error=error_msg)

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