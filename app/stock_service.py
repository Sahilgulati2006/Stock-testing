import yfinance as yf
from datetime import date, timedelta, datetime
import pandas as pd
import numpy as np
from polygon import RESTClient
from app.config import Config
import time

client = RESTClient(Config.POLYGON_API_KEY)

class StockService:
    @staticmethod
    def get_stock_data(ticker):
        """Fetch stock data for the given ticker"""
        def fetch_from_polygon():
            """Helper function to fetch data from Polygon"""
            max_retries = 3
            base_delay = 3  # Increased base delay
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        delay = base_delay * (2 ** (attempt - 1))  # 3, 6, 12 seconds
                        print(f"Polygon API: Retry attempt {attempt + 1}, waiting {delay} seconds...")
                        time.sleep(delay)
                    
                    # Test API connection
                    client.get_ticker_details(ticker)
                    print("Polygon API connection successful")
                    
                    # Fetch the data
                    aggs = client.get_aggs(ticker, 1, "day", start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                    if not aggs:
                        raise ValueError("No data returned from Polygon API")
                    
                    return pd.DataFrame([{
                        'Date': datetime.fromtimestamp(a.timestamp/1000),
                        'Open': a.open,
                        'High': a.high,
                        'Low': a.low,
                        'Close': a.close,
                        'Volume': a.volume
                    } for a in aggs]).set_index('Date').sort_index()
                    
                except Exception as e:
                    print(f"Polygon attempt {attempt + 1} failed: {str(e)}")
                    if "429" in str(e) and attempt < max_retries - 1:
                        continue
                    if attempt == max_retries - 1:
                        raise
            
            return None

        def fetch_from_yfinance():
            """Helper function to fetch data from Yahoo Finance"""
            print("\nFalling back to Yahoo Finance API...")
            # Get extra days for better EMA calculation
            start = start_date - timedelta(days=100)
            data = yf.download(ticker, start=start, end=end_date, progress=False)
            if data.empty:
                raise ValueError("No data available from Yahoo Finance")
            print("Successfully fetched data from Yahoo Finance")
            return data

        try:
            print(f"\nFetching stock data for {ticker}")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)  # Get 1 year of data
            print(f"Date range: {start_date.date()} to {end_date.date()}")
            
            # Try Polygon first
            try:
                df = fetch_from_polygon()
                if df is not None:
                    print("Successfully fetched data from Polygon API")
                else:
                    print("No data from Polygon, trying Yahoo Finance...")
                    df = fetch_from_yfinance()
            except Exception as e:
                print(f"Polygon API failed: {str(e)}")
                print("Falling back to Yahoo Finance...")
                df = fetch_from_yfinance()
            
            # Verify data quality
            if df.empty:
                raise ValueError(f"Empty dataset returned for {ticker}")
            
            print(f"DataFrame shape: {df.shape}")
            print(f"Date range in data: {df.index.min().date()} to {df.index.max().date()}")
            print(f"Columns: {df.columns.tolist()}")
            print(f"Sample of Close prices: {df['Close'].head()}")
            
            if df['Close'].isnull().all():
                raise ValueError(f"No valid close prices for {ticker}")
            
            return df
            
        except Exception as e:
            print(f"Error in get_stock_data for {ticker}: {str(e)}")
            print(f"Exception type: {type(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            raise ValueError(f"Could not fetch stock data for {ticker}: {str(e)}")
    
    @staticmethod
    def calculate_technical_indicators(data):
        """Calculate technical indicators including EMAs and RSI"""
        try:
            print("Starting technical indicator calculations...")
            df = data.copy()
            
            # Handle any NaN values
            df['Close'] = df['Close'].fillna(method='ffill')
            print(f"Close price range: {df['Close'].min()} to {df['Close'].max()}")
            
            # Calculate EMAs
            df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['EMA_100'] = df['Close'].ewm(span=100, adjust=False).mean()
            
            print("EMAs calculated successfully")
            
            # RSI Calculation
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            print("RSI calculated successfully")
            
            # Calculate EMA crossovers
            df['EMA_50_100_Cross'] = np.where(
                df['EMA_50'] > df['EMA_100'], 1, -1
            )
            df['EMA_Cross_Change'] = df['EMA_50_100_Cross'].diff()
            
            # Identify trend
            df['Trend'] = np.where(
                (df['Close'] > df['EMA_50']) & (df['EMA_50'] > df['EMA_100']), 
                'Bullish',
                np.where(
                    (df['Close'] < df['EMA_50']) & (df['EMA_50'] < df['EMA_100']),
                    'Bearish',
                    'Neutral'
                )
            )
            
            # Clean up any NaN values
            df = df.fillna(method='ffill').fillna(method='bfill')
            
            # Get last 50 days of data
            result = df.tail(50)
            print(f"Final processed data shape: {result.shape}")
            return result
            
        except Exception as e:
            print(f"Error in technical indicators calculation: {str(e)}")
            print(f"Data state: {df.head() if 'df' in locals() else 'DataFrame not created'}")
            raise
    
    @staticmethod
    def analyze_trends(data):
        """Analyze current market trends and signals"""
        try:
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            
            analysis = {
                'current_trend': latest['Trend'],
                'rsi_value': round(latest['RSI'], 2),
                'rsi_signal': 'Oversold' if latest['RSI'] < 30 else 'Overbought' if latest['RSI'] > 70 else 'Neutral',
                'ema_signal': 'Bullish' if latest['EMA_50'] > latest['EMA_100'] else 'Bearish',
                'price': round(latest['Close'], 2),
                'ema_50': round(latest['EMA_50'], 2),
                'ema_100': round(latest['EMA_100'], 2)
            }
            
            # Check for recent EMA crossover
            if latest['EMA_Cross_Change'] == 2:  # Bullish crossover
                analysis['cross_alert'] = "Recent bullish crossover: EMA-50 crossed above EMA-100"
            elif latest['EMA_Cross_Change'] == -2:  # Bearish crossover
                analysis['cross_alert'] = "Recent bearish crossover: EMA-50 crossed below EMA-100"
            else:
                analysis['cross_alert'] = None
                
            return analysis
            
        except Exception as e:
            print(f"Error analyzing trends: {e}")
            return None
    
    @staticmethod
    def calculate_fibonacci_levels(data):
        """Calculate Fibonacci retracement levels"""
        try:
            if data is None or data.empty:
                return None
                
            high = float(data['High'].max())
            low = float(data['Low'].min())
            close = float(data['Close'].iloc[-1])
            diff = high - low
            
            levels = {
                'Current': close,
                '0.0 (High)': high,
                '23.6%': high - (0.236 * diff),
                '38.2%': high - (0.382 * diff),
                '50.0%': high - (0.5 * diff),
                '61.8%': high - (0.618 * diff),
                '100.0 (Low)': low
            }
            
            # Convert all values to float and round to 2 decimal places
            return {k: round(float(v), 2) for k, v in levels.items()}
            
        except Exception as e:
            print(f"Error calculating Fibonacci levels: {e}")
            return None
    
    @staticmethod
    def get_stock_news(ticker, limit=5):
        """Fetch recent news for a stock"""
        try:
            print(f"\nFetching news for {ticker}")
            
            # Initial delay and retry settings
            max_retries = 3
            base_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # Add delay between attempts (exponential backoff)
                    if attempt > 0:
                        delay = base_delay * (2 ** (attempt - 1))  # 2, 4, 8 seconds
                        print(f"Retry attempt {attempt + 1}, waiting {delay} seconds...")
                        time.sleep(delay)
                    
                    # Fetch news with specific parameters
                    news = client.list_ticker_news(
                        ticker=ticker,
                        limit=limit,
                        order='desc',
                        sort='published_utc'
                    )
                    
                    news_items = []
                    for item in news:
                        # Convert UTC timestamp to readable date
                        try:
                            published_date = datetime.fromtimestamp(item.published_utc/1000).strftime('%Y-%m-%d %H:%M UTC')
                        except:
                            published_date = 'Date not available'
                        
                        # Truncate description to avoid very long text
                        description = getattr(item, 'description', 'No description available')
                        if description and len(description) > 200:
                            description = description[:197] + '...'
                        
                        news_item = {
                            "title": getattr(item, 'title', 'No title available'),
                            "description": description,
                            "published": published_date,
                            "url": getattr(item, 'article_url', '#')
                        }
                        news_items.append(news_item)
                    
                    if news_items:
                        print(f"Successfully fetched {len(news_items)} news items for {ticker}")
                        return news_items
                    else:
                        return [{
                            "title": "No recent news available",
                            "description": f"No news articles found for {ticker}",
                            "published": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                            "url": "#"
                        }]
                
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {str(e)}")
                    if attempt == max_retries - 1:  # Last attempt
                        raise
                    if "429" in str(e):  # Rate limit error
                        continue
                    else:  # Other error
                        raise
            
        except Exception as e:
            print(f"Error fetching news for {ticker}: {str(e)}")
            return [{
                "title": "News temporarily unavailable",
                "description": "We're experiencing some technical difficulties fetching the latest news. Please try again in a few minutes.",
                "published": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                "url": "#"
            }]
    
    @staticmethod
    def get_fundamentals(ticker):
        """Fetch fundamental data"""
        try:
            print(f"\nFetching fundamentals for {ticker}")
            details = client.get_ticker_details(ticker)
            fundamentals = {
                "name": details.name if hasattr(details, 'name') else ticker,
                "industry": details.sic_description if hasattr(details, 'sic_description') else "N/A",
                "market_cap": details.market_cap if hasattr(details, 'market_cap') else "N/A",
                "description": details.description if hasattr(details, 'description') else "No description available"
            }
            print(f"Successfully retrieved fundamentals for {ticker}")
            return fundamentals
        except Exception as e:
            print(f"Error fetching fundamentals for {ticker}: {e}")
            return {
                "name": ticker,
                "industry": "N/A",
                "market_cap": "N/A",
                "description": "Data unavailable"
            }