from flask import Blueprint, jsonify, request, render_template, redirect, url_for, session
import yfinance as yf
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.sentiment_service import SentimentService
from app.stock_service import StockService
from app.portfolio_service import PortfolioService
from app.storage_service import StorageService
from functools import lru_cache
from app.web_search import web_search

main = Blueprint('main', __name__)
portfolio_service = PortfolioService()
stock_service = StockService()
storage_service = StorageService()

# Cache sentiment results for 1 hour to avoid repeated Reddit API calls
@lru_cache(maxsize=100)
def get_cached_sentiment(subreddit, ticker, timestamp):
    """Cache sentiment results with a timestamp to expire after 1 hour"""
    try:
        sentiment_service = SentimentService()
        sentiment_data = sentiment_service.analyze_subreddit(subreddit)
        if sentiment_data and ticker in dict(sentiment_data.get('top_stocks', [])):
            return sentiment_data
    except Exception as e:
        print(f"Error getting sentiment data: {str(e)}")
    return None

@main.route('/api/sentiment/<ticker>')
def get_sentiment(ticker):
    """API endpoint to get sentiment data for a ticker"""
    try:
        # Initialize sentiment service
        sentiment_service = SentimentService()
        
        # Get the selected subreddit from the query parameters, default to wallstreetbets
        selected_subreddit = request.args.get('subreddit', 'wallstreetbets')
        
        # Get current hour for caching
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        
        # Get sentiment data for the selected subreddit only
        sentiment_data = get_cached_sentiment(selected_subreddit, ticker.upper(), current_hour)
        
        if sentiment_data and sentiment_data.get('sentiment_results'):
            return jsonify({
                'success': True,
                'data': {
                    'sentiment_results': sentiment_data['sentiment_results'],
                    'subreddit_data': {
                        selected_subreddit: sentiment_data['sentiment_results'].get(ticker.upper(), {})
                    }
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No sentiment data found for {ticker} in r/{selected_subreddit}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/analyze', methods=['GET', 'POST'])
def analyze():
    # Get ticker from either POST form data or GET query parameter
    if request.method == 'POST':
        ticker = request.form.get('ticker', '').upper()
    else:
        ticker = request.args.get('ticker', '').upper()
    
    if not ticker:
        return redirect(url_for('main.home'))
        
    try:
        # Get stock data and calculate indicators
        stock_data = stock_service.get_stock_data(ticker)
        stock_data = stock_service.calculate_technical_indicators(stock_data)
        
        # Analyze trends
        trend_analysis = stock_service.analyze_trends(stock_data)
        
        # Calculate Fibonacci levels
        fib_levels = stock_service.calculate_fibonacci_levels(stock_data)
        
        # Get news and fundamentals
        news = stock_service.get_stock_news(ticker)
        fundamentals = stock_service.get_fundamentals(ticker)
        
        # Get competitor data
        competitor_data = stock_service.get_competitors(ticker)
        
        # Get similar stock recommendations
        similar_stocks = stock_service.get_similar_stocks(ticker)
        
        # Convert DataFrame to records for chart
        stock_records = []
        for idx, row in stock_data.iterrows():
            try:
                record = {
                    'Date': idx.strftime('%Y-%m-%d'),
                    'Open': float(row['Open']),
                    'High': float(row['High']),
                    'Low': float(row['Low']),
                    'Close': float(row['Close']),
                    'Volume': float(row['Volume']),
                    'EMA_20': float(row['EMA_20']),
                    'EMA_50': float(row['EMA_50']),
                    'EMA_100': float(row['EMA_100']),
                    'RSI': float(row['RSI'])
                }
                stock_records.append(record)
            except Exception as e:
                print(f"Error processing row for {ticker} at {idx}: {str(e)}")
                continue
        
        if not stock_records:
            raise ValueError(f"No valid stock data could be processed for {ticker}")
        
        # Sort records by date
        stock_records.sort(key=lambda x: x['Date'])
        
        return render_template('analysis.html', 
                             ticker=ticker,
                             stock_data=stock_records,
                             trend_analysis=trend_analysis,
                             fib_levels=fib_levels,
                             news=news,
                             fundamentals=fundamentals,
                             similar_stocks=similar_stocks,
                             competitor_data=competitor_data)
                             
    except Exception as e:
        error_msg = f"Error analyzing {ticker}: {str(e)}"
        print(f"ERROR: {error_msg}")
        return render_template('analysis.html',
                             ticker=ticker,
                             error=error_msg)

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

@main.route('/portfolio')
def portfolio():
    """Portfolio dashboard page"""
    try:
        # Load portfolio data from storage
        portfolio_data = storage_service.load_portfolio()
        
        # Calculate portfolio metrics
        metrics = portfolio_service.calculate_portfolio_metrics(portfolio_data)
        
        # Render template with metrics
        return render_template('portfolio.html',
                             portfolio_data=portfolio_data,
                             metrics=metrics)
                             
    except Exception as e:
        print(f"Error in portfolio route: {str(e)}")
        return render_template('portfolio.html',
                             portfolio_data={'positions': [], 'cash': 0.0},
                             metrics={
                                 'total_value': 0.0,
                                 'positions': [],
                                 'metrics': {
                                     'daily_return': 0.0,
                                     'weekly_return': 0.0,
                                     'monthly_return': 0.0,
                                     'yearly_return': 0.0,
                                     'volatility': 0.0,
                                     'total_growth': 0.0,
                                     'beta': 1.0,
                                     'var_95': 0.0
                                 }
                             })

@main.route('/api/portfolio/add-position', methods=['POST'])
def add_position():
    """Add a new position to the portfolio"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        shares = float(data.get('shares', 0))
        cost_basis = float(data.get('cost_basis', 0))
        
        if not all([ticker, shares > 0, cost_basis > 0]):
            return jsonify({'error': 'Invalid position data'}), 400
            
        # Verify stock exists
        stock_data = stock_service.get_stock_data(ticker)
        if stock_data is None:
            return jsonify({'error': f'Could not fetch stock data for {ticker}'}), 400
        
        # Load current portfolio
        portfolio_data = storage_service.load_portfolio()
        
        # Check if position already exists
        for position in portfolio_data['positions']:
            if position['ticker'] == ticker:
                # Update existing position with weighted average cost basis
                total_shares = position['shares'] + shares
                total_cost = (position['shares'] * position['cost_basis']) + (shares * cost_basis)
                position['shares'] = total_shares
                position['cost_basis'] = total_cost / total_shares
                break
        else:
            # Add new position
            portfolio_data['positions'].append({
                'ticker': ticker,
                'shares': shares,
                'cost_basis': cost_basis
            })
        
        # Save updated portfolio
        storage_service.save_portfolio(portfolio_data)
        
        return jsonify({'success': True, 'message': 'Position added successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/portfolio/remove-position', methods=['POST'])
def remove_position():
    """Remove a position from the portfolio"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        
        if not ticker:
            return jsonify({'error': 'No ticker provided'}), 400
        
        # Load current portfolio
        portfolio_data = storage_service.load_portfolio()
        
        # Remove position
        portfolio_data['positions'] = [p for p in portfolio_data['positions'] if p['ticker'] != ticker]
        
        # Save updated portfolio
        storage_service.save_portfolio(portfolio_data)
        
        return jsonify({'success': True, 'message': 'Position removed successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/portfolio/update-position', methods=['POST'])
def update_position():
    """Update an existing position"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        shares = float(data.get('shares', 0))
        cost_basis = float(data.get('cost_basis', 0))
        
        if not all([ticker, shares, cost_basis]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        portfolio_data = storage_service.load_portfolio()
        
        # Update position
        for position in portfolio_data['positions']:
            if position['ticker'] == ticker:
                position['shares'] = shares
                position['cost_basis'] = cost_basis
                break
        else:
            return jsonify({'error': f'Position not found: {ticker}'}), 404
            
        # Save updated portfolio
        storage_service.save_portfolio(portfolio_data)
        
        return jsonify({'success': True, 'message': 'Position updated successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/portfolio/metrics')
def get_portfolio_metrics():
    """Get updated portfolio metrics"""
    try:
        # Load portfolio data from storage
        portfolio_data = storage_service.load_portfolio()
        
        # Calculate and return metrics
        metrics = portfolio_service.calculate_portfolio_metrics(portfolio_data)
        return jsonify(metrics)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/portfolio/optimize')
def optimize_portfolio():
    """Get portfolio optimization suggestions"""
    try:
        portfolio_service = PortfolioService()
        portfolio_data = storage_service.load_portfolio()
        
        if not portfolio_data['positions']:
            return jsonify({'error': 'No positions in portfolio'}), 404
            
        risk_tolerance = request.args.get('risk_tolerance', 'moderate')
        optimization_data = portfolio_service.optimize_portfolio(portfolio_data, risk_tolerance)
        return jsonify(optimization_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/portfolio-analysis')
def portfolio_analysis():
    return redirect(url_for('main.portfolio'))

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
        print(f"Error in what-if calculator: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/portfolio/news')
def get_portfolio_news():
    """Get latest news for portfolio stocks"""
    try:
        from app.tools import web_search
        
        # Load portfolio data from storage
        portfolio_data = storage_service.load_portfolio()
        if not portfolio_data.get('positions'):
            return jsonify([])
        
        all_news = []
        # Get news for each stock in portfolio
        for position in portfolio_data['positions']:
            ticker = position['ticker']
            try:
                # Search for recent news about the stock
                search_query = f"{ticker} stock market news"
                news_results = web_search(search_query, explanation=f"Fetching news for {ticker}")
                
                # Format the news results
                if isinstance(news_results, list):
                    for result in news_results:
                        news_item = {
                            'ticker': ticker,
                            'title': result.get('title', f'News about {ticker}'),
                            'summary': result.get('snippet', 'No summary available'),
                            'url': result.get('url', '#'),
                            'date': result.get('date', 'Recent')
                        }
                        all_news.append(news_item)
            except Exception as e:
                print(f"Error fetching news for {ticker}: {str(e)}")
                # Add a fallback news item
                all_news.append({
                    'ticker': ticker,
                    'title': f'Market updates for {ticker}',
                    'summary': 'Unable to fetch latest news. Please try again later.',
                    'url': f'https://finance.yahoo.com/quote/{ticker}',
                    'date': 'Recent'
                })
        
        return jsonify(all_news)
        
    except Exception as e:
        print(f"Error in portfolio news route: {str(e)}")
        return jsonify([{
            'ticker': 'System',
            'title': 'News Service Temporarily Unavailable',
            'summary': 'We are unable to fetch news at the moment. Please try again later.',
            'url': '#',
            'date': 'Now'
        }])

@main.route('/api/portfolio/events')
def get_portfolio_events():
    """Get upcoming earnings and significant events for portfolio stocks"""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        # Load portfolio data from storage
        portfolio_data = storage_service.load_portfolio()
        if not portfolio_data.get('positions'):
            return jsonify([])
        
        all_events = []
        # Get events for each stock in portfolio
        for position in portfolio_data['positions']:
            ticker = position['ticker']
            try:
                # Get stock info using yfinance
                stock = yf.Ticker(ticker)
                stock_info = stock.info
                company_name = stock_info.get('longName', ticker)
                
                # Get earnings information
                try:
                    # Get current and estimated EPS
                    eps_data = {
                        'current_eps': stock_info.get('trailingEps', 'N/A'),
                        'estimated_eps': stock_info.get('forwardEps', 'N/A'),
                        'eps_growth': stock_info.get('earningsQuarterlyGrowth', 'N/A')
                    }
                    
                    # Get analyst price targets
                    analyst_data = {
                        'current_price': stock_info.get('regularMarketPrice', 'N/A'),
                        'target_mean': stock_info.get('targetMeanPrice', 'N/A'),
                        'target_high': stock_info.get('targetHighPrice', 'N/A'),
                        'target_low': stock_info.get('targetLowPrice', 'N/A'),
                        'target_median': stock_info.get('targetMedianPrice', 'N/A'),
                        'number_of_analysts': stock_info.get('numberOfAnalystOpinions', 'N/A'),
                        'recommendation': stock_info.get('recommendationKey', 'N/A').capitalize(),
                        'upside_potential': None
                    }
                    
                    # Calculate upside potential if we have both current price and mean target
                    if (analyst_data['current_price'] != 'N/A' and 
                        analyst_data['target_mean'] != 'N/A' and
                        analyst_data['current_price'] > 0):
                        analyst_data['upside_potential'] = (
                            (analyst_data['target_mean'] - analyst_data['current_price']) / 
                            analyst_data['current_price'] * 100
                        )
                    
                    # Generate AI summary of financial performance
                    summary = generate_financial_summary(stock_info)
                    
                    # Try to get next earnings date
                    if 'earningsDate' in stock_info:
                        earnings_timestamp = stock_info['earningsDate']
                        if isinstance(earnings_timestamp, list) and earnings_timestamp:
                            earnings_date = datetime.fromtimestamp(earnings_timestamp[0])
                            
                            # Only add if earnings date is in the future
                            if earnings_date > datetime.now():
                                quarter = (earnings_date.month-1)//3 + 1
                                fiscal_year = earnings_date.year
                                all_events.append({
                                    'ticker': ticker,
                                    'type': 'Earnings Call',
                                    'date': earnings_date.strftime('%Y-%m-%d'),
                                    'description': f'Q{quarter} {fiscal_year} Earnings Release',
                                    'details': {
                                        'event_type': 'Earnings Call',
                                        'company': company_name,
                                        'quarter': f'Q{quarter} {fiscal_year}',
                                        'date': earnings_date.strftime('%B %d, %Y'),
                                        'time': 'After Market Close',
                                        'current_eps': f"${eps_data['current_eps']}" if eps_data['current_eps'] != 'N/A' else 'N/A',
                                        'estimated_eps': f"${eps_data['estimated_eps']}" if eps_data['estimated_eps'] != 'N/A' else 'N/A',
                                        'eps_growth': f"{eps_data['eps_growth']}%" if eps_data['eps_growth'] != 'N/A' else 'N/A',
                                        'financial_summary': summary,
                                        'analyst_targets': analyst_data,
                                        'key_metrics': {
                                            'revenue_growth': stock_info.get('revenueGrowth', 'N/A'),
                                            'profit_margins': stock_info.get('profitMargins', 'N/A'),
                                            'operating_margins': stock_info.get('operatingMargins', 'N/A'),
                                            'return_on_equity': stock_info.get('returnOnEquity', 'N/A'),
                                            'debt_to_equity': stock_info.get('debtToEquity', 'N/A')
                                        }
                                    }
                                })
                    
                    # Add placeholder if no earnings date found but we have EPS data
                    elif eps_data['estimated_eps'] != 'N/A':
                        all_events.append({
                            'ticker': ticker,
                            'type': 'EPS Update',
                            'date': 'Upcoming',
                            'description': f"Est. EPS: ${eps_data['estimated_eps']}",
                            'details': {
                                'event_type': 'EPS Update',
                                'company': company_name,
                                'current_eps': f"${eps_data['current_eps']}" if eps_data['current_eps'] != 'N/A' else 'N/A',
                                'estimated_eps': f"${eps_data['estimated_eps']}" if eps_data['estimated_eps'] != 'N/A' else 'N/A',
                                'eps_growth': f"{eps_data['eps_growth']}%" if eps_data['eps_growth'] != 'N/A' else 'N/A',
                                'financial_summary': summary,
                                'analyst_targets': analyst_data,
                                'key_metrics': {
                                    'revenue_growth': stock_info.get('revenueGrowth', 'N/A'),
                                    'profit_margins': stock_info.get('profitMargins', 'N/A'),
                                    'operating_margins': stock_info.get('operatingMargins', 'N/A'),
                                    'return_on_equity': stock_info.get('returnOnEquity', 'N/A'),
                                    'debt_to_equity': stock_info.get('debtToEquity', 'N/A')
                                }
                            }
                        })
                        
                except Exception as e:
                    print(f"Error getting earnings info for {ticker}: {str(e)}")
                    
            except Exception as e:
                print(f"Error fetching events for {ticker}: {str(e)}")
                continue
        
        # Sort events by date
        all_events.sort(key=lambda x: x['date'] if x['date'] != 'Upcoming' else '9999-12-31')
        
        return jsonify(all_events)
        
    except Exception as e:
        print(f"Error in portfolio events route: {str(e)}")
        return jsonify([{
            'ticker': 'System',
            'type': 'Error',
            'date': 'Now',
            'description': 'Unable to fetch events. Please try again later.',
            'details': {
                'event_type': 'Error',
                'message': str(e),
                'timestamp': datetime.now().strftime('%B %d, %Y %H:%M:%S')
            }
        }])

def generate_financial_summary(stock_info):
    """Generate an AI summary of the company's financial performance"""
    try:
        # Extract key metrics
        metrics = {
            'revenue_growth': stock_info.get('revenueGrowth', 'N/A'),
            'profit_margins': stock_info.get('profitMargins', 'N/A'),
            'operating_margins': stock_info.get('operatingMargins', 'N/A'),
            'return_on_equity': stock_info.get('returnOnEquity', 'N/A'),
            'debt_to_equity': stock_info.get('debtToEquity', 'N/A'),
            'forward_pe': stock_info.get('forwardPE', 'N/A'),
            'trailing_pe': stock_info.get('trailingPE', 'N/A'),
            'price_to_book': stock_info.get('priceToBook', 'N/A'),
            'beta': stock_info.get('beta', 'N/A')
        }
        
        # Generate summary based on metrics
        summary = []
        
        if metrics['revenue_growth'] not in ['N/A', None]:
            growth = metrics['revenue_growth'] * 100
            summary.append(f"Revenue growth is {growth:.1f}%, indicating {'strong' if growth > 10 else 'moderate' if growth > 0 else 'negative'} top-line expansion.")
        
        if metrics['profit_margins'] not in ['N/A', None]:
            margins = metrics['profit_margins'] * 100
            summary.append(f"Profit margins at {margins:.1f}% suggest {'excellent' if margins > 20 else 'good' if margins > 10 else 'fair' if margins > 5 else 'concerning'} profitability.")
        
        if metrics['return_on_equity'] not in ['N/A', None]:
            roe = metrics['return_on_equity'] * 100
            summary.append(f"Return on equity of {roe:.1f}% shows {'very efficient' if roe > 20 else 'efficient' if roe > 15 else 'moderate' if roe > 10 else 'inefficient'} use of shareholder capital.")
        
        if metrics['debt_to_equity'] not in ['N/A', None]:
            summary.append(f"Debt-to-equity ratio of {metrics['debt_to_equity']:.2f} indicates {'high' if metrics['debt_to_equity'] > 2 else 'moderate' if metrics['debt_to_equity'] > 1 else 'conservative'} leverage.")
        
        if metrics['forward_pe'] not in ['N/A', None]:
            summary.append(f"Forward P/E of {metrics['forward_pe']:.1f} suggests the stock is {'expensive' if metrics['forward_pe'] > 25 else 'reasonably valued' if metrics['forward_pe'] > 15 else 'potentially undervalued'} relative to earnings expectations.")
        
        # Join summaries with proper spacing
        return " ".join(summary) if summary else "Insufficient data to generate a financial summary."
        
    except Exception as e:
        print(f"Error generating financial summary: {str(e)}")
        return "Unable to generate financial summary due to insufficient data." 