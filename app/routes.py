from flask import Blueprint, jsonify, request, render_template, redirect, url_for
import yfinance as yf
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.sentiment_service import SentimentService

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/analyze', methods=['POST'])
def analyze():
    ticker = request.form.get('ticker', '').upper()
    if not ticker:
        return redirect(url_for('main.home'))
    return render_template('analysis.html', ticker=ticker)

@main.route('/sentiment-analysis', methods=['GET', 'POST'])
def sentiment_analysis():
    if request.method == 'POST':
        subreddit = request.form.get('subreddit', 'wallstreetbets')
        sentiment_service = SentimentService()
        try:
            analysis = sentiment_service.analyze_subreddit(subreddit)
            return render_template('sentiment.html', analysis=analysis)
        except Exception as e:
            return render_template('sentiment.html', error=str(e))
    
    return render_template('sentiment.html')

@main.route('/portfolio-analysis')
def portfolio_analysis():
    return render_template('portfolio.html')

@main.route('/api/what-if-calculator', methods=['POST'])
def what_if_calculator():
    try:
        data = request.get_json()
        initial_investment = float(data.get('initial_investment', 0))
        ticker = data.get('ticker', '').upper()
        start_date = datetime.strptime(data.get('start_date', ''), '%Y-%m-%d')
        
        if not all([initial_investment, ticker, start_date]):
            return jsonify({'error': 'Missing required parameters'}), 400
            
        # Get historical data from start date to today
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date)
        
        if hist.empty:
            return jsonify({'error': f'No historical data available for {ticker}'}), 404
            
        # Calculate returns
        start_price = hist.iloc[0]['Close']
        current_price = hist.iloc[-1]['Close']
        
        # Calculate investment values
        shares = initial_investment / start_price
        current_value = shares * current_price
        
        # Calculate returns
        total_return = current_value - initial_investment
        total_return_percentage = (total_return / initial_investment) * 100
        
        # Calculate time period
        today = datetime.now()
        years = relativedelta(today, start_date).years
        months = relativedelta(today, start_date).months
        
        if years > 0:
            time_period = f"{years} year{'s' if years != 1 else ''}"
            if months > 0:
                time_period += f", {months} month{'s' if months != 1 else ''}"
        else:
            time_period = f"{months} month{'s' if months != 1 else ''}"
            
        # Calculate annualized return
        total_years = years + (months / 12)
        if total_years > 0:
            annual_return = ((current_value / initial_investment) ** (1 / total_years) - 1) * 100
        else:
            annual_return = total_return_percentage
            
        return jsonify({
            'current_value': current_value,
            'total_return_percentage': total_return_percentage,
            'time_period': time_period,
            'annual_return': annual_return
        })
        
    except Exception as e:
        print(f"Error in what-if calculator: {str(e)}")  # Add logging
        return jsonify({'error': str(e)}), 500 