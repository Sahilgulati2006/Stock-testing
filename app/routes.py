from flask import Blueprint, jsonify, request, render_template, redirect, url_for, session
import yfinance as yf
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.sentiment_service import SentimentService
from app.stock_service import StockService
from app.portfolio_service import PortfolioService
from app.postgres_storage_service import PostgresStorageService
from app.market_sentiment_service import MarketSentimentService
from app.warren_buffett_ai import WarrenBuffettAI
from functools import lru_cache
from app.web_search import web_search
import time

main = Blueprint('main', __name__)
portfolio_service = PortfolioService()
stock_service = StockService()
storage_service = PostgresStorageService()
market_sentiment_service = MarketSentimentService()
warren_ai = WarrenBuffettAI()

# Cache market indices data for 5 minutes
market_indices_cache = {}
market_indices_cache_time = {}

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
        timeframe = request.form.get('timeframe', 'day')  # Default to past 24 hours
        sentiment_service = SentimentService()
        try:
            print(f"\nStarting sentiment analysis for r/{subreddit} with timeframe: {timeframe}")
            analysis = sentiment_service.analyze_subreddit(subreddit, timeframe=timeframe)
            
            # Debug print to verify data
            print(f"Processed posts: {len(analysis.get('processed_posts', []))}")
            print(f"Top stocks found: {len(analysis.get('top_stocks', []))}")
            
            return render_template('sentiment.html', analysis=analysis)
        except Exception as e:
            print(f"Error in sentiment analysis: {str(e)}")
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
        ticker = data.get('ticker')
        start_date = data.get('start_date')
        investment_type = data.get('investment_type', 'lumpsum')
        
        if not ticker or not start_date:
            return jsonify({
                'error': 'Please provide both ticker and start date'
            })
        
        # Convert start_date string to datetime
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        current_date = datetime.now()
        
        if start_date > current_date:
            return jsonify({
                'error': 'Start date cannot be in the future'
            })
            
        # Get historical data
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date)
            
            if hist.empty:
                return jsonify({
                    'error': f'No historical data available for {ticker}'
                })
                
            # Ensure we have the closing price data
            if 'Close' not in hist.columns:
                return jsonify({
                    'error': f'Price data unavailable for {ticker}'
                })
        except Exception as e:
            print(f"Error fetching stock data: {str(e)}")
            return jsonify({
                'error': f'Unable to fetch data for {ticker}. Please try again.'
            })
        
        if investment_type == 'lumpsum':
            try:
                initial_investment = float(data.get('initial_investment', 0))
                if initial_investment <= 0:
                    return jsonify({
                        'error': 'Initial investment must be greater than 0'
                    })
                
                # Calculate returns for lump sum investment
                first_price = hist['Close'].iloc[0]
                last_price = hist['Close'].iloc[-1]
                shares = initial_investment / first_price
                current_value = shares * last_price
                total_return = ((current_value - initial_investment) / initial_investment) * 100
                
                # Calculate XIRR
                dates = [start_date, current_date]
                cashflows = [-initial_investment, current_value]
                xirr = calculate_xirr(dates, cashflows)
                
                return jsonify({
                    'current_value': current_value,
                    'total_return_percentage': total_return,
                    'total_invested': initial_investment,
                    'xirr': xirr
                })
            except Exception as e:
                print(f"Error in lump sum calculation: {str(e)}")
                return jsonify({
                    'error': 'Error calculating lump sum returns. Please check your inputs.'
                })
            
        elif investment_type == 'sip':
            try:
                monthly_investment = float(data.get('monthly_investment', 0))
                initial_investment = float(data.get('initial_investment', 0))
                
                if monthly_investment <= 0:
                    return jsonify({
                        'error': 'Monthly investment must be greater than 0'
                    })
                
                # Calculate SIP returns
                total_invested = initial_investment
                current_value = 0
                dates = []
                cashflows = []
                total_shares = 0
                
                # Initial investment
                if initial_investment > 0:
                    first_price = hist['Close'].iloc[0]
                    shares = initial_investment / first_price
                    total_shares += shares
                    dates.append(start_date)
                    cashflows.append(-initial_investment)
                
                # Monthly investments
                current_month = start_date
                
                while current_month <= current_date:
                    # Get the month's data
                    month_mask = (hist.index.year == current_month.year) & (hist.index.month == current_month.month)
                    month_data = hist[month_mask]
                    
                    if not month_data.empty:
                        # Use the average price for the month
                        month_price = month_data['Close'].mean()
                        shares = monthly_investment / month_price
                        total_shares += shares
                        total_invested += monthly_investment
                        
                        # Add to cashflow for XIRR calculation
                        dates.append(current_month)
                        cashflows.append(-monthly_investment)
                    
                    # Move to next month
                    current_month = current_month + relativedelta(months=1)
                
                # Calculate final value
                if total_shares > 0:
                    current_value = total_shares * hist['Close'].iloc[-1]
                    
                    # Add final value for XIRR calculation
                    dates.append(current_date)
                    cashflows.append(current_value)
                    
                    # Calculate returns
                    if total_invested > 0:
                        total_return = ((current_value - total_invested) / total_invested) * 100
                        xirr = calculate_xirr(dates, cashflows)
                    else:
                        total_return = 0
                        xirr = 0
                        
                    return jsonify({
                        'current_value': current_value,
                        'total_return_percentage': total_return,
                        'total_invested': total_invested,
                        'xirr': xirr
                    })
                else:
                    return jsonify({
                        'error': 'No investments were made in the specified period'
                    })
                    
            except Exception as e:
                print(f"Error in SIP calculation: {str(e)}")
                return jsonify({
                    'error': 'Error calculating SIP returns. Please check your inputs.'
                })
        else:
            return jsonify({
                'error': 'Invalid investment type'
            })
            
    except Exception as e:
        print(f"Error in what_if_calculator: {str(e)}")
        return jsonify({
            'error': 'An error occurred while calculating returns. Please try again.'
        })

def calculate_xirr(dates, cashflows):
    """Calculate the XIRR given dates and cashflows"""
    try:
        years = [(date - dates[0]).days / 365 for date in dates]
        
        def xnpv(rate):
            return sum([cf / (1 + rate) ** year for cf, year in zip(cashflows, years)])
            
        def xirr_objective(rate):
            return xnpv(rate)
            
        from scipy.optimize import newton
        rate = newton(xirr_objective, x0=0.1)
        return rate * 100
    except:
        return 0  # Return 0 if XIRR calculation fails

@main.route('/api/portfolio/news')
def get_portfolio_news():
    """Get latest news for portfolio stocks"""
    try:
        from app.tools import web_search
        from app.stock_service import StockService
        
        # Load portfolio data from storage
        portfolio_data = storage_service.load_portfolio()
        if not portfolio_data.get('positions'):
            return jsonify([])
        
        all_news = []
        # Get news for each stock in portfolio
        for position in portfolio_data['positions']:
            ticker = position['ticker']
            try:
                # First try to get news using StockService (which uses Yahoo Finance API)
                news_items = StockService.get_stock_news(ticker, limit=3)
                if news_items and not news_items[0]['url'].startswith('#'):
                    for item in news_items:
                        news_item = {
                            'ticker': ticker,
                            'title': item['title'],
                            'summary': item['description'],
                            'url': item['url'],
                            'date': item['published']
                        }
                        all_news.append(news_item)
                    continue

                # Fallback to web search if Yahoo Finance API doesn't return valid news
                search_query = f"{ticker} stock market news"
                news_results = web_search(search_query, explanation=f"Fetching news for {ticker}")
                
                # Format the news results
                if isinstance(news_results, list):
                    for result in news_results:
                        if result.get('url', '#') != '#':  # Only add if we have a valid URL
                            news_item = {
                                'ticker': ticker,
                                'title': result.get('title', f'News about {ticker}'),
                                'summary': result.get('snippet', 'No summary available'),
                                'url': result.get('url'),
                                'date': result.get('date', 'Recent')
                            }
                            all_news.append(news_item)
            except Exception as e:
                print(f"Error fetching news for {ticker}: {str(e)}")
                # Try one more time with a different search query
                try:
                    search_query = f"{ticker} company news latest"
                    news_results = web_search(search_query, explanation=f"Retrying news fetch for {ticker}")
                    if isinstance(news_results, list) and news_results and news_results[0].get('url', '#') != '#':
                        news_item = {
                            'ticker': ticker,
                            'title': news_results[0].get('title', f'News about {ticker}'),
                            'summary': news_results[0].get('snippet', 'No summary available'),
                            'url': news_results[0].get('url'),
                            'date': news_results[0].get('date', 'Recent')
                        }
                        all_news.append(news_item)
                except:
                    # Only add fallback if we couldn't get any real news
                    all_news.append({
                        'ticker': ticker,
                        'title': f'No recent news found for {ticker}',
                        'summary': 'Please check back later for updates.',
                        'url': f'https://finance.yahoo.com/quote/{ticker}/news',  # Link to news section instead of main page
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

@main.route('/api/market-sentiment')
def get_market_sentiment():
    """Get the current market sentiment (Fear & Greed Index)"""
    try:
        sentiment_data = market_sentiment_service.get_fear_greed_index()
        return jsonify(sentiment_data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'value': 50,
            'category': 'Neutral',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'signals': ['Error fetching market sentiment'],
            'indicators': {
                'vix': 50,
                'momentum': 50,
                'volume': 50
            }
        }), 500 

@main.route('/api/warren-buffett/analyze-stock', methods=['POST'])
def analyze_stock():
    """Get Warren Buffett's analysis of a specific stock"""
    try:
        data = request.get_json()
        ticker = data.get('ticker')
        if not ticker:
            return jsonify({'error': 'No ticker provided'}), 400
            
        analysis = warren_ai.analyze_stock(ticker)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'analysis': ["I always say you should invest in what you understand. Right now, I'm having trouble understanding this situation."],
            'quote': "Risk comes from not knowing what you're doing."
        }), 500

@main.route('/api/warren-buffett/portfolio-advice')
def get_portfolio_advice():
    """Get Warren Buffett's advice on your portfolio"""
    try:
        portfolio_data = portfolio_service.get_portfolio_data()
        advice = warren_ai.get_advice(portfolio_data)
        return jsonify(advice)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'advice': ["The most important thing in investing is to know what you're doing. If you're unsure, consider index funds."],
            'wisdom_quote': "Risk comes from not knowing what you're doing."
        }), 500 

@main.route('/api/warren-buffett/chat', methods=['POST'])
def chat_with_warren():
    """Chat with Warren Buffett AI"""
    try:
        data = request.get_json()
        message = data.get('message')
        if not message:
            return jsonify({'error': 'No message provided'}), 400
            
        # Get portfolio data for context if available
        try:
            portfolio_data = portfolio_service.get_portfolio_data()
        except:
            portfolio_data = None
            
        context = {'portfolio_data': portfolio_data} if portfolio_data else {}
        
        # Get response from Warren AI
        response = warren_ai.get_conversation_response(message, context)
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'response': "Even the best investors face uncertainty sometimes. Could you rephrase your question?",
            'type': 'error'
        }), 500 

@main.route('/api/market/indices')
def get_market_indices():
    """Get real-time data for major market indices using their ETF equivalents"""
    try:
        # Check if we have cached data that's less than 5 minutes old
        current_time = time.time()
        if 'market_indices' in market_indices_cache and current_time - market_indices_cache_time.get('market_indices', 0) < 300:  # 5 minutes = 300 seconds
            print("Returning cached market indices data")
            return jsonify(market_indices_cache['market_indices'])
        
        print("Starting to fetch market indices data...")
        
        # Define the ETFs that track major indices
        indices = {
            'SPY': 'SPY',  # S&P 500 ETF
            'QQQ': 'QQQ',  # NASDAQ 100 ETF
            'DIA': 'DIA',  # Dow Jones ETF
            'IWM': 'IWM'   # Russell 2000 ETF
        }
        
        result = {}
        
        # Try to fetch data from Yahoo Finance using a different approach
        try:
            print("Attempting to fetch data from Yahoo Finance using a different approach...")
            
            # Use a different method to fetch data - try using the Ticker object directly
            for symbol in indices:
                try:
                    print(f"Fetching data for {symbol}...")
                    
                    # Add a delay between requests to avoid rate limiting
                    time.sleep(2)
                    
                    # Create a Ticker object
                    ticker = yf.Ticker(symbol)
                    
                    # Try to get the current price using the info property
                    try:
                        print(f"Getting info for {symbol}...")
                        info = ticker.info
                        
                        if info and 'regularMarketPrice' in info:
                            print(f"Got info data for {symbol}")
                            current_price = float(info.get('regularMarketPrice', 0))
                            open_price = float(info.get('regularMarketOpen', 0))
                            high_price = float(info.get('regularMarketDayHigh', 0))
                            low_price = float(info.get('regularMarketDayLow', 0))
                            
                            # If high or low are 0, set reasonable values based on current price
                            if high_price == 0 and current_price > 0:
                                high_price = current_price * 1.01  # 1% higher than current
                            
                            if low_price == 0 and current_price > 0:
                                low_price = current_price * 0.99  # 1% lower than current
                                
                            # Ensure high is not less than current or open
                            high_price = max(high_price, current_price, open_price)
                            
                            # Ensure low is not higher than current or open
                            if low_price > 0:  # Only if we have a valid low price
                                low_price = min(low_price, current_price, open_price) if open_price > 0 else min(low_price, current_price)
                            
                            result[symbol] = {
                                'current': current_price,
                                'open': open_price,
                                'high': high_price,
                                'low': low_price,
                                'volume': int(info.get('regularMarketVolume', 0))
                            }
                            print(f"Processed info data for {symbol}: {result[symbol]}")
                            continue
                    except Exception as e:
                        print(f"Info method failed for {symbol}: {str(e)}")
                    
                    # If info method fails, try history with a specific interval
                    try:
                        print(f"Trying history method for {symbol}...")
                        # Use 1d interval for the most recent data
                        hist = ticker.history(interval='1d', period='1d')
                        
                        if not hist.empty:
                            print(f"Got data for {symbol} using history method")
                            current_price = float(hist['Close'].iloc[-1])
                            open_price = float(hist['Open'].iloc[0])
                            high_price = float(hist['High'].max())
                            low_price = float(hist['Low'].min())
                            
                            # If high or low are 0, set reasonable values based on current price
                            if high_price == 0 and current_price > 0:
                                high_price = current_price * 1.01  # 1% higher than current
                            
                            if low_price == 0 and current_price > 0:
                                low_price = current_price * 0.99  # 1% lower than current
                                
                            # Ensure high is not less than current or open
                            high_price = max(high_price, current_price, open_price)
                            
                            # Ensure low is not higher than current or open
                            if low_price > 0:  # Only if we have a valid low price
                                low_price = min(low_price, current_price, open_price) if open_price > 0 else min(low_price, current_price)
                            
                            result[symbol] = {
                                'current': current_price,
                                'open': open_price,
                                'high': high_price,
                                'low': low_price,
                                'volume': int(hist['Volume'].sum())
                            }
                            print(f"Processed data for {symbol}: {result[symbol]}")
                        else:
                            print(f"No data available for {symbol}")
                    except Exception as e:
                        print(f"History method failed for {symbol}: {str(e)}")
                        
                        # Try with a different interval if 1d fails
                        try:
                            print(f"Trying history method with 5d period for {symbol}...")
                            hist = ticker.history(period='5d')
                            
                            if not hist.empty:
                                print(f"Got data for {symbol} using 5d history method")
                                current_price = float(hist['Close'].iloc[-1])
                                open_price = float(hist['Open'].iloc[-1])
                                high_price = float(hist['High'].iloc[-1])
                                low_price = float(hist['Low'].iloc[-1])
                                
                                # If high or low are 0, set reasonable values based on current price
                                if high_price == 0 and current_price > 0:
                                    high_price = current_price * 1.01  # 1% higher than current
                                
                                if low_price == 0 and current_price > 0:
                                    low_price = current_price * 0.99  # 1% lower than current
                                    
                                # Ensure high is not less than current or open
                                high_price = max(high_price, current_price, open_price)
                                
                                # Ensure low is not higher than current or open
                                if low_price > 0:  # Only if we have a valid low price
                                    low_price = min(low_price, current_price, open_price) if open_price > 0 else min(low_price, current_price)
                                
                                result[symbol] = {
                                    'current': current_price,
                                    'open': open_price,
                                    'high': high_price,
                                    'low': low_price,
                                    'volume': int(hist['Volume'].iloc[-1])
                                }
                                print(f"Processed data for {symbol}: {result[symbol]}")
                            else:
                                print(f"No data available for {symbol} with 5d period")
                        except Exception as e:
                            print(f"5d history method failed for {symbol}: {str(e)}")
                            
                except Exception as e:
                    print(f"Error processing {symbol}: {str(e)}")
        except Exception as e:
            print(f"Error fetching data from Yahoo Finance: {str(e)}")
        
        # If we couldn't get any data from Yahoo Finance, return an error
        if not result:
            print("No data could be retrieved from Yahoo Finance")
            return jsonify({
                'error': 'Unable to fetch market indices data. Please try again later.',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }), 503
        
        # Cache the result
        market_indices_cache['market_indices'] = result
        market_indices_cache_time['market_indices'] = current_time
        
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"Error in get_market_indices: {str(e)}"
        print(error_msg)
        return jsonify({
            'error': 'An error occurred while fetching market indices data.',
            'details': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 500

@main.route('/api/fibonacci-from-point', methods=['POST'])
def calculate_fibonacci_from_point():
    """Calculate Fibonacci levels from a selected point"""
    try:
        # Add CORS headers
        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
            return ('', 204, headers)

        # Add CORS headers to the response
        response_headers = {
            'Access-Control-Allow-Origin': '*'
        }
        
        data = request.get_json()
        ticker = data.get('ticker')
        selected_date = data.get('selected_date')
        
        if not ticker or not selected_date:
            return jsonify({
                'error': 'Please provide both ticker and selected date'
            }), 400, response_headers
            
        # Get stock data
        stock_data = stock_service.get_stock_data(ticker)
        if stock_data is None:
            return jsonify({
                'error': f'Could not fetch data for {ticker}'
            }), 404, response_headers
            
        # Calculate Fibonacci levels from the selected point
        fib_levels = stock_service.calculate_fibonacci_from_point(stock_data, selected_date)
        
        if fib_levels is None:
            return jsonify({
                'error': 'Could not calculate Fibonacci levels'
            }), 400, response_headers
            
        return jsonify({
            'success': True,
            'levels': fib_levels
        }), 200, response_headers
        
    except Exception as e:
        print(f"Error calculating Fibonacci levels: {str(e)}")
        return jsonify({
            'error': 'An error occurred while calculating Fibonacci levels'
        }), 500, response_headers 