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
            try:
                # Single attempt to fetch data from Polygon
                aggs = client.get_aggs(ticker, 1, "day", start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                if not aggs:
                    return None
                
                return pd.DataFrame([{
                    'Date': datetime.fromtimestamp(a.timestamp/1000),
                    'Open': a.open,
                    'High': a.high,
                    'Low': a.low,
                    'Close': a.close,
                    'Volume': a.volume
                } for a in aggs]).set_index('Date').sort_index()
                
            except Exception as e:
                print(f"Polygon API failed: {str(e)}")
                return None

        def fetch_from_yfinance():
            """Helper function to fetch data from Yahoo Finance"""
            print("\nFetching from Yahoo Finance API...")
            # Get extra days for better EMA calculation
            start = start_date - timedelta(days=200)  # Add 200 extra days for better EMA calculation
            data = yf.download(ticker, start=start, end=end_date, progress=False)
            if len(data.index) == 0:  # Check if DataFrame is empty using len
                raise ValueError("No data available from Yahoo Finance")
            print(f"Successfully fetched data from Yahoo Finance ({len(data)} days)")
            return data

        try:
            print(f"\nFetching stock data for {ticker}")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # Get 2 years of data
            
            # Try Polygon first, then fall back to Yahoo Finance
            df = fetch_from_polygon()
            if df is None or len(df.index) == 0:
                print("No data from Polygon, using Yahoo Finance...")
                df = fetch_from_yfinance()
            
            # Verify data quality
            if len(df.index) == 0:  # Check if DataFrame is empty using len
                raise ValueError(f"Empty dataset returned for {ticker}")
            
            print(f"DataFrame shape: {df.shape}")
            print(f"Date range in data: {df.index.min().date()} to {df.index.max().date()}")
            print(f"Columns: {df.columns.tolist()}")
            
            # Check for valid close prices
            if df['Close'].isnull().all().item():  # Use .item() to get scalar boolean
                raise ValueError(f"No valid close prices for {ticker}")
            
            # Sort the data to ensure it's in chronological order
            df = df.sort_index()
            
            # Ensure we have enough data for technical analysis
            if len(df) < 100:
                raise ValueError(f"Insufficient data points for {ticker} (minimum 100 required)")
            
            return df
            
        except Exception as e:
            print(f"Error in get_stock_data for {ticker}: {str(e)}")
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
            
            # Calculate RSI
            delta = df['Close'].diff()
            gain = delta.copy()
            loss = delta.copy()
            gain[gain < 0] = 0
            loss[loss > 0] = 0
            
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = abs(loss.rolling(window=14).mean())
            
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
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
            
            print(f"Final processed data shape: {df.shape}")
            return df
            
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
        if data is None or data.empty:
            return None
        
        try:
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
            
            return {k: round(float(v), 2) for k, v in levels.items()}
            
        except Exception as e:
            print(f"Error calculating Fibonacci levels: {e}")
            return None
            
    @staticmethod
    def calculate_fibonacci_from_point(data, selected_date):
        """Calculate Fibonacci retracement levels from a selected point to the subsequent high"""
        if data is None or data.empty:
            return None
            
        try:
            # Convert selected_date to datetime if it's a string
            if isinstance(selected_date, str):
                selected_date = pd.to_datetime(selected_date)
                
            # Get data from selected point onwards
            mask = data.index >= selected_date
            future_data = data[mask]
            
            if future_data.empty:
                return None
                
            # Get the selected point's price and the maximum price after it
            selected_price = float(future_data['Close'].iloc[0])
            max_price = float(future_data['High'].max())
            current_price = float(future_data['Close'].iloc[-1])
            
            # Calculate the price difference
            diff = max_price - selected_price
            
            # Calculate Fibonacci levels
            levels = {
                'Current': current_price,
                '0.0 (Selected Point)': selected_price,
                '23.6%': selected_price + (0.236 * diff),
                '38.2%': selected_price + (0.382 * diff),
                '50.0%': selected_price + (0.5 * diff),
                '61.8%': selected_price + (0.618 * diff),
                '78.6%': selected_price + (0.786 * diff),
                '100.0 (High)': max_price,
                'Selected Date': selected_date.strftime('%Y-%m-%d'),
                'Max Price Date': future_data[future_data['High'] == max_price].index[0].strftime('%Y-%m-%d')
            }
            
            return {k: round(float(v), 2) if k not in ['Selected Date', 'Max Price Date'] else v 
                   for k, v in levels.items()}
                   
        except Exception as e:
            print(f"Error calculating Fibonacci levels from point: {e}")
            return None
    
    @staticmethod
    def get_stock_news(ticker, limit=5):
        """Fetch recent news for a stock using Yahoo Finance"""
        try:
            print(f"\nFetching news for {ticker} from Yahoo Finance")
            
            # Create a Yahoo Finance ticker object
            yf_ticker = yf.Ticker(ticker)
            
            # Get news from Yahoo Finance
            news_data = yf_ticker.news
            
            if not news_data:
                return [{
                    "title": "No recent news available",
                    "description": f"No news articles found for {ticker}",
                    "published": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                    "url": "#",
                    "source": "Yahoo Finance"
                }]
            
            # Process and format news items
            news_items = []
            for item in news_data[:limit]:  # Limit to requested number of items
                try:
                    # Get the content dictionary
                    content = item.get('content', item)  # Some items might be nested under 'content'
                    
                    # Get timestamp from pubDate
                    pub_date = content.get('pubDate')
                    if pub_date:
                        try:
                            # Parse the ISO format date
                            published_date = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%SZ')
                        except:
                            published_date = datetime.now()
                    else:
                        published_date = datetime.now()
                    
                    # Get the publisher
                    provider = content.get('provider', {})
                    publisher = provider.get('displayName', 'Yahoo Finance')
                    
                    # Get title
                    title = content.get('title', '').strip()
                    if not title:
                        continue
                    
                    # Get description/summary
                    description = content.get('summary', content.get('description', '')).strip()
                    if not description:
                        continue
                        
                    if len(description) > 200:
                        description = description[:197] + '...'
                    
                    # Get URL - try different possible locations
                    url = (content.get('canonicalUrl', {}).get('url') or 
                          content.get('url') or 
                          content.get('link') or 
                          content.get('previewUrl'))
                    
                    if not url:
                        continue
                    
                    news_item = {
                        "title": title,
                        "description": description,
                        "published": published_date.strftime('%Y-%m-%d %H:%M UTC'),
                        "url": url,
                        "source": publisher
                    }
                    news_items.append(news_item)
                except Exception as e:
                    print(f"Error processing news item: {str(e)}")
                    continue
            
            if not news_items:
                return [{
                    "title": "No valid news available",
                    "description": f"Could not find any valid news articles for {ticker}",
                    "published": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                    "url": "#",
                    "source": "Yahoo Finance"
                }]
            
            print(f"Successfully fetched {len(news_items)} news items for {ticker}")
            return news_items
            
        except Exception as e:
            print(f"Error fetching news for {ticker}: {str(e)}")
            return [{
                "title": "News temporarily unavailable",
                "description": "We're experiencing some technical difficulties fetching the latest news. Please try again later.",
                "published": datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
                "url": "#",
                "source": "Yahoo Finance"
            }]
    
    @staticmethod
    def get_fundamentals(ticker):
        """Fetch fundamental data and financial metrics"""
        def format_number(num):
            """Helper to format large numbers"""
            if num is None or num == 0:
                return "N/A"
            if num >= 1e12:
                return f"${num/1e12:.2f}T"
            elif num >= 1e9:
                return f"${num/1e9:.2f}B"
            elif num >= 1e6:
                return f"${num/1e6:.2f}M"
            else:
                return f"${num:,.0f}"

        def calculate_ratios(info):
            """Calculate financial ratios"""
            try:
                pe_ratio = info.get('trailingPE', 0)
                forward_pe = info.get('forwardPE', 0)
                
                # Calculate PEG ratio
                # First try to get pegRatio directly
                peg_ratio = info.get('pegRatio', 0)
                
                # If pegRatio is not available, calculate it using PE and earnings growth
                if not peg_ratio or peg_ratio == 0:
                    earnings_growth = info.get('earningsGrowth', 0)
                    if earnings_growth and earnings_growth != 0 and pe_ratio and pe_ratio > 0:
                        peg_ratio = pe_ratio / (earnings_growth * 100)
                    else:
                        # Try using earnings quarterly growth
                        earnings_quarterly_growth = info.get('earningsQuarterlyGrowth', 0)
                        if earnings_quarterly_growth and earnings_quarterly_growth != 0 and pe_ratio and pe_ratio > 0:
                            peg_ratio = pe_ratio / (earnings_quarterly_growth * 100)
                
                price_to_book = info.get('priceToBook', 0)
                
                return {
                    'PE Ratio': f"{pe_ratio:.2f}" if pe_ratio and pe_ratio > 0 else "N/A",
                    'Forward PE': f"{forward_pe:.2f}" if forward_pe and forward_pe > 0 else "N/A",
                    'PEG Ratio': f"{peg_ratio:.2f}" if peg_ratio and peg_ratio > 0 else "N/A",
                    'Price/Book': f"{price_to_book:.2f}" if price_to_book and price_to_book > 0 else "N/A"
                }
            except Exception as e:
                print(f"Error calculating ratios: {str(e)}")
                return {
                    'PE Ratio': "N/A",
                    'Forward PE': "N/A",
                    'PEG Ratio': "N/A",
                    'Price/Book': "N/A"
                }

        def analyze_financials(info, ratios):
            """Analyze financial metrics and provide recommendations"""
            analysis = []
            score = 0
            max_score = 0
            
            # Store metrics for time horizon analysis
            metrics = {
                'pe_ratio': 0,
                'peg_ratio': 0,
                'revenue_growth': 0,
                'profit_margins': 0,
                'beta': info.get('beta', 1),
                'earnings_growth': info.get('earningsGrowth', 0),
                'recommendation_trend': info.get('recommendationKey', '').lower()
            }
            
            # PE Ratio Analysis
            try:
                pe = float(ratios['PE Ratio'].replace("N/A", "0"))
                metrics['pe_ratio'] = pe
                if 0 < pe < 15:
                    analysis.append("✅ PE Ratio indicates stock might be undervalued")
                    score += 1
                elif 15 <= pe < 25:
                    analysis.append("📊 PE Ratio is within reasonable range")
                    score += 0.5
                elif pe >= 25:
                    analysis.append("⚠️ PE Ratio suggests stock might be overvalued")
                max_score += 1
            except:
                pass

            # PEG Ratio Analysis
            try:
                peg = float(ratios['PEG Ratio'].replace("N/A", "0"))
                metrics['peg_ratio'] = peg
                if 0 < peg < 1:
                    analysis.append("✅ PEG Ratio suggests good value relative to growth")
                    score += 1
                elif 1 <= peg < 2:
                    analysis.append("📊 PEG Ratio indicates fair value")
                    score += 0.5
                elif peg >= 2:
                    analysis.append("⚠️ PEG Ratio suggests stock might be overvalued")
                max_score += 1
            except:
                pass

            # Price to Book Analysis
            try:
                pb = float(ratios['Price/Book'].replace("N/A", "0"))
                if 0 < pb < 3:
                    analysis.append("✅ Price/Book ratio suggests reasonable valuation")
                    score += 1
                elif 3 <= pb < 5:
                    analysis.append("📊 Price/Book ratio is moderate")
                    score += 0.5
                elif pb >= 5:
                    analysis.append("⚠️ High Price/Book ratio")
                max_score += 1
            except:
                pass

            # Revenue Growth
            try:
                revenue_growth = info.get('revenueGrowth', 0)
                metrics['revenue_growth'] = revenue_growth
                if revenue_growth > 0.2:
                    analysis.append("✅ Strong revenue growth (>20%)")
                    score += 1
                elif 0.05 <= revenue_growth <= 0.2:
                    analysis.append("📊 Moderate revenue growth (5-20%)")
                    score += 0.5
                elif revenue_growth < 0.05:
                    analysis.append("⚠️ Low revenue growth (<5%)")
                max_score += 1
            except:
                pass

            # Profit Margins
            try:
                profit_margins = info.get('profitMargins', 0)
                metrics['profit_margins'] = profit_margins
                if profit_margins > 0.2:
                    analysis.append("✅ Strong profit margins (>20%)")
                    score += 1
                elif 0.1 <= profit_margins <= 0.2:
                    analysis.append("📊 Healthy profit margins (10-20%)")
                    score += 0.5
                elif profit_margins < 0.1:
                    analysis.append("⚠️ Low profit margins (<10%)")
                max_score += 1
            except:
                pass

            # Calculate final score and recommendation
            if max_score > 0:
                final_score = (score / max_score) * 100
                if final_score >= 70:
                    recommendation = "🟢 Strong Buy - Financial metrics indicate strong fundamentals"
                elif final_score >= 50:
                    recommendation = "🟡 Hold - Financial metrics are mixed but generally positive"
                else:
                    recommendation = "🔴 Caution - Financial metrics suggest careful consideration needed"
            else:
                recommendation = "⚪ Unable to make recommendation - Insufficient financial data"

            return {
                'analysis_points': analysis,
                'recommendation': recommendation,
                'score': f"{final_score:.1f}%" if max_score > 0 else "N/A",
                'metrics': metrics  # Add metrics to the return value
            }

        def analyze_time_horizon(metrics, info):
            """Analyze and provide time horizon recommendations"""
            long_term_score = 0
            short_term_score = 0
            
            # Long-term factors (positive values indicate better long-term outlook)
            if metrics['revenue_growth'] > 0.1:  # Good revenue growth
                long_term_score += 2
            if metrics['earnings_growth'] > 0.1:  # Good earnings growth
                long_term_score += 2
            if metrics['profit_margins'] > 0.15:  # Healthy margins
                long_term_score += 1
            if 0 < metrics['peg_ratio'] < 1.5:  # Good growth at reasonable price
                long_term_score += 2
            
            # Short-term factors (negative values indicate higher short-term risk)
            if metrics['beta'] > 1.2:  # High volatility
                short_term_score -= 1
            if metrics['pe_ratio'] > 30:  # High valuation
                short_term_score -= 1
            if metrics['recommendation_trend'] in ['sell', 'underperform']:
                short_term_score -= 1
            
            # Generate outlook messages
            long_term_outlook = "Strong AI & data center growth potential positions the stock well for long-term investors."
            if long_term_score >= 4:
                long_term_outlook = "Excellent long-term potential with strong growth metrics and healthy fundamentals."
            elif long_term_score >= 2:
                long_term_outlook = "Moderate long-term potential with some positive growth indicators."
            else:
                long_term_outlook = "Long-term outlook requires careful monitoring of growth metrics."

            short_term_outlook = "High valuation + bearish trend = Short-term volatility expected."
            if short_term_score < -2:
                short_term_outlook = "High risk of short-term volatility due to current market conditions and metrics."
            elif short_term_score < -1:
                short_term_outlook = "Moderate short-term volatility expected based on current indicators."
            else:
                short_term_outlook = "Short-term outlook is relatively stable but monitor market conditions."

            return {
                'long_term_outlook': long_term_outlook,
                'short_term_outlook': short_term_outlook
            }

        try:
            print(f"\nFetching fundamentals for {ticker}")
            
            # Try Yahoo Finance first for more detailed financials
            try:
                print("Fetching fundamentals from Yahoo Finance...")
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Get current price and price change
                current_price = info.get('currentPrice', 0)
                previous_close = info.get('previousClose', current_price)
                price_change = current_price - previous_close
                price_change_percent = (price_change / previous_close) * 100 if previous_close else 0
                
                # Get basic info
                fundamentals = {
                    "name": info.get('longName', ticker),
                    "industry": info.get('industry', "N/A"),
                    "sector": info.get('sector', "N/A"),
                    "market_cap": format_number(info.get('marketCap', 0)),
                    "description": info.get('longBusinessSummary', "No description available"),
                    
                    # Add price information
                    "current_price": current_price,
                    "price_change": price_change,
                    "price_change_percent": price_change_percent,
                    
                    # Company Overview Data
                    "company_name": info.get('longName', ticker),
                    "headquarters": f"{info.get('city', 'N/A')}, {info.get('state', '')}, {info.get('country', '')}".replace(", ,", ",").strip(", "),
                    "ceo": info.get('companyOfficers', [{}])[0].get('name', 'N/A') if info.get('companyOfficers') else 'N/A',
                    "ceo_title": info.get('companyOfficers', [{}])[0].get('title', 'CEO') if info.get('companyOfficers') else 'CEO',
                    "business_summary": info.get('longBusinessSummary', "No business summary available."),
                    "global_presence": info.get('geographySegments', "Global operations") if info.get('geographySegments') else "N/A",
                    
                    # Products and Services
                    "products_services": [
                        segment.strip()
                        for segment in info.get('businessSegments', "").split(",")
                        if segment.strip()
                    ] if info.get('businessSegments') else [],
                    
                    # Key Markets
                    "key_markets": [
                        {
                            "name": "Consumer Market",
                            "description": "Individual consumers and retail customers"
                        },
                        {
                            "name": info.get('sector', 'Primary Sector'),
                            "description": info.get('industry', 'Main industry focus')
                        },
                        {
                            "name": "Geographic Markets",
                            "description": info.get('geographySegments', 'Global operations')
                        }
                    ] if info.get('sector') or info.get('industry') else [
                        {
                            "name": "Primary Market",
                            "description": info.get('longBusinessSummary', '').split('.')[0] if info.get('longBusinessSummary') else "Main business segment"
                        }
                    ],
                    
                    # Major Holders
                    "major_holders": [],
                    
                    # Additional financial metrics
                    "revenue": format_number(info.get('totalRevenue', 0)),
                    "revenue_growth": f"{info.get('revenueGrowth', 0)*100:.1f}%" if info.get('revenueGrowth') else "N/A",
                    "profit_margin": f"{info.get('profitMargins', 0)*100:.1f}%" if info.get('profitMargins') else "N/A",
                    "operating_margin": f"{info.get('operatingMargins', 0)*100:.1f}%" if info.get('operatingMargins') else "N/A",
                    "free_cashflow": format_number(info.get('freeCashflow', 0)),
                    "debt_to_equity": f"{info.get('debtToEquity', 0):.2f}" if info.get('debtToEquity') else "N/A",
                    "current_ratio": f"{info.get('currentRatio', 0):.2f}" if info.get('currentRatio') else "N/A",
                    
                    # Calculate key ratios
                    "ratios": calculate_ratios(info)
                }
                
                # Calculate ratios
                ratios = calculate_ratios(info)
                fundamentals['ratios'] = ratios
                
                # Analyze financials
                analysis_results = analyze_financials(info, ratios)
                fundamentals.update(analysis_results)
                
                # Add time horizon analysis
                time_horizon = analyze_time_horizon(analysis_results['metrics'], info)
                fundamentals.update(time_horizon)
                
                # Add competitor analysis
                competitors = []
                competitor_symbols = {
                    'NVDA': ['AMD', 'INTC', 'QCOM'],
                    'AAPL': ['MSFT', 'GOOGL', 'SSNLF'],
                    'TSLA': ['GM', 'F', 'TM'],
                    'META': ['GOOGL', 'SNAP', 'PINS'],
                    'MSFT': ['AAPL', 'GOOGL', 'ORCL']
                }
                
                if ticker in competitor_symbols:
                    for symbol in competitor_symbols[ticker]:
                        try:
                            comp_stock = yf.Ticker(symbol)
                            comp_info = comp_stock.info
                            
                            competitors.append({
                                'symbol': symbol,
                                'pe_ratio': f"{comp_info.get('trailingPE', 0):.1f}",
                                'profit_margin': f"{comp_info.get('profitMargins', 0) * 100:.1f}%",
                                'revenue_growth': f"{comp_info.get('revenueGrowth', 0) * 100:.1f}%"
                            })
                        except Exception as e:
                            print(f"Error fetching competitor data for {symbol}: {str(e)}")
                            continue
                
                fundamentals['competitors'] = competitors
                
                # Add competitor insights
                if competitors:
                    insights = []
                    try:
                        # PE Ratio comparison
                        company_pe = float(fundamentals['ratios'].get('PE Ratio', '0').replace(',', ''))
                        comp_pes = [float(c['pe_ratio']) for c in competitors if c['pe_ratio'] != 'N/A']
                        
                        # Revenue Growth comparison
                        company_growth = float(fundamentals['revenue_growth'].strip('%'))
                        comp_growths = [float(c['revenue_growth'].strip('%')) for c in competitors if c['revenue_growth'] != 'N/A']
                        
                        # Profit Margin comparison
                        company_margin = float(fundamentals['profit_margin'].strip('%'))
                        comp_margins = [float(c['profit_margin'].strip('%')) for c in competitors if c['profit_margin'] != 'N/A']
                        
                        # Industry Position Analysis
                        if comp_pes:
                            avg_pe = sum(comp_pes) / len(comp_pes)
                            if company_pe > avg_pe * 1.2:
                                insights.append(f"{ticker} trades at a premium PE ratio compared to competitors, suggesting higher growth expectations.")
                            elif company_pe < avg_pe * 0.8:
                                insights.append(f"{ticker} trades at a discount PE ratio compared to competitors, potentially indicating undervaluation.")
                        
                        if comp_growths:
                            avg_growth = sum(comp_growths) / len(comp_growths)
                            growth_rank = sum(1 for g in comp_growths if g < company_growth) + 1
                            total_companies = len(comp_growths) + 1
                            insights.append(f"Revenue Growth: Ranks #{growth_rank} out of {total_companies} in the peer group.")
                            
                            if company_growth > avg_growth * 1.5:
                                insights.append(f"Industry Leader: {ticker} shows exceptional revenue growth, significantly outpacing industry average.")
                            elif company_growth < avg_growth * 0.5:
                                insights.append(f"Growth Challenge: {ticker}'s revenue growth is notably below industry average.")
                        
                        if comp_margins:
                            avg_margin = sum(comp_margins) / len(comp_margins)
                            margin_rank = sum(1 for m in comp_margins if m < company_margin) + 1
                            total_companies = len(comp_margins) + 1
                            insights.append(f"Profit Margin: Ranks #{margin_rank} out of {total_companies} in the peer group.")
                            
                            if company_margin > avg_margin * 1.2:
                                insights.append(f"Strong Profitability: {ticker} demonstrates superior profit margins compared to peers.")
                            elif company_margin < avg_margin * 0.8:
                                insights.append(f"Margin Pressure: {ticker} faces profitability challenges relative to industry standards.")
                        
                        fundamentals['competitor_insights'] = insights
                        
                    except Exception as e:
                        print(f"Error generating insights: {str(e)}")
                        fundamentals['competitor_insights'] = ["Unable to generate competitor insights due to data limitations."]
                
                # Major Holders
                major_holders = []
                
                # Add institutional holders
                institutional_holders = stock.institutional_holders
                if institutional_holders is not None and not institutional_holders.empty:
                    for _, holder in institutional_holders.head(3).iterrows():
                        shares_held = holder.get('Shares', 0)
                        shares_out = info.get('sharesOutstanding', 0)
                        percentage = (shares_held / shares_out * 100) if shares_out > 0 else 0
                        major_holders.append({
                            "name": holder.get('Holder', 'Unknown Institution'),
                            "type": "Institution",
                            "percentage": f"{percentage:.1f}%",
                            "shares": format_number(shares_held)
                        })
                
                # Add major holders
                major_holders_data = stock.major_holders
                if major_holders_data is not None and not major_holders_data.empty:
                    for _, row in major_holders_data.iterrows():
                        if len(row) >= 2:  # Ensure we have both percentage and holder type
                            percentage = row[0].strip().rstrip('%')  # Remove % symbol and whitespace
                            holder_type = row[1]
                            if "insiders" in holder_type.lower():
                                major_holders.append({
                                    "name": "Company Insiders",
                                    "type": "Insiders",
                                    "percentage": f"{float(percentage):.1f}%",
                                    "shares": "N/A"
                                })
                            elif "institutions" in holder_type.lower():
                                major_holders.append({
                                    "name": "Total Institutional Holdings",
                                    "type": "Institutions",
                                    "percentage": f"{float(percentage):.1f}%",
                                    "shares": "N/A"
                                })
                
                fundamentals["major_holders"] = major_holders
                
                print("Successfully fetched fundamentals from Yahoo Finance")
                return fundamentals
                
            except Exception as e:
                print(f"Yahoo Finance fundamentals fetch failed: {str(e)}")
                
                # Try Polygon as backup
                try:
                    print("Attempting to fetch fundamentals from Polygon API...")
                    details = client.get_ticker_details(ticker)
                    fundamentals = {
                        "name": details.name if hasattr(details, 'name') else ticker,
                        "industry": details.sic_description if hasattr(details, 'sic_description') else "N/A",
                        "market_cap": format_number(details.market_cap if hasattr(details, 'market_cap') else 0),
                        "description": details.description if hasattr(details, 'description') else "No description available",
                        
                        # Company Overview Data
                        "company_name": details.name if hasattr(details, 'name') else ticker,
                        "headquarters": f"{details.locale if hasattr(details, 'locale') else 'N/A'}",
                        "ceo": "N/A",  # Polygon doesn't provide CEO info
                        "ceo_title": "CEO",
                        "business_summary": details.description if hasattr(details, 'description') else "No business summary available.",
                        "global_presence": details.locale if hasattr(details, 'locale') else "N/A",
                        
                        # Products and Services
                        "products_services": [
                            details.sic_description
                        ] if hasattr(details, 'sic_description') else [],
                        
                        # Key Markets
                        "key_markets": [
                            {
                                "name": "Consumer Market",
                                "description": "Individual consumers and retail customers"
                            },
                            {
                                "name": details.sic_description if hasattr(details, 'sic_description') else "Primary Market",
                                "description": details.sic_description if hasattr(details, 'sic_description') else "Main business segment"
                            },
                            {
                                "name": "Geographic Markets",
                                "description": details.locale if hasattr(details, 'locale') else "Global operations"
                            }
                        ] if details.sic_description or details.locale else [
                            {
                                "name": "Primary Market",
                                "description": details.description if hasattr(details, 'description') else "Main business segment"
                            }
                        ],
                        
                        # Major Holders (Polygon doesn't provide this)
                        "major_holders": [],
                        
                        "ratios": {
                            'PE Ratio': "N/A",
                            'Forward PE': "N/A",
                            'PEG Ratio': "N/A",
                            'Price/Book': "N/A"
                        },
                        'analysis_points': ["Unable to fetch detailed financial metrics"],
                        'recommendation': "⚪ Unable to make recommendation - Insufficient financial data",
                        'score': "N/A"
                    }
                    return fundamentals
                except Exception as e:
                    print(f"Polygon API fundamentals fetch failed: {str(e)}")
                    raise
            
        except Exception as e:
            print(f"Error in get_fundamentals for {ticker}: {str(e)}")
            return {
                "name": ticker,
                "industry": "N/A",
                "market_cap": "N/A",
                "description": "Data temporarily unavailable",
                "ratios": {
                    'PE Ratio': "N/A",
                    'Forward PE': "N/A",
                    'PEG Ratio': "N/A",
                    'Price/Book': "N/A"
                },
                'analysis_points': ["Unable to fetch financial metrics"],
                'recommendation': "⚪ Unable to make recommendation - Insufficient financial data",
                'score': "N/A"
            }

    @staticmethod
    def calculate_rsi(df):
        """Calculate RSI (Relative Strength Index)"""
        if df is None or len(df) < 14:
            return None, "Neutral"

        try:
            delta = df['Close'].diff()
            gain = delta.copy()
            loss = delta.copy()
            gain[gain < 0] = 0
            loss[loss > 0] = 0
            
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = abs(loss.rolling(window=14).mean())
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            latest_rsi = rsi.iloc[-1]
            
            if latest_rsi > 70:
                rsi_signal = "Overbought"
            elif latest_rsi < 30:
                rsi_signal = "Oversold"
            else:
                rsi_signal = "Neutral"
            
            return latest_rsi, rsi_signal
        except Exception as e:
            print(f"Error calculating RSI: {str(e)}")
            return None, "Neutral"

    def get_technical_analysis(self, df):
        """Get technical analysis including RSI"""
        try:
            latest_rsi, rsi_signal = self.calculate_rsi(df)
            return {
                'rsi_value': latest_rsi,
                'rsi_signal': rsi_signal
            }
        except Exception as e:
            print(f"Error in technical analysis: {str(e)}")
            return {
                'rsi_value': None,
                'rsi_signal': "Neutral"
            }

    @staticmethod
    def get_similar_stocks(ticker):
        """Get similar stock recommendations based on sector, industry, and market cap"""
        try:
            print(f"\nFinding similar stocks for {ticker}")
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get sector and industry
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            market_cap = info.get('marketCap', 0)
            
            if not sector or not industry:
                return None
                
            print(f"Finding stocks in {sector} - {industry}")
            
            # Define stock categories
            categories = {
                'growth': {
                    'description': 'Growth Focused',
                    'stocks': []
                },
                'value': {
                    'description': 'Value Focused',
                    'stocks': []
                }
            }
            
            # Get similar stocks in the same industry
            similar_stocks = []
            
            # Predefined mappings for major sectors
            tech_growth = ['NVDA', 'AMD', 'TSMC']
            tech_value = ['INTC', 'QCOM', 'TXN']
            
            finance_growth = ['V', 'MA', 'PYPL']
            finance_value = ['JPM', 'BAC', 'WFC']
            
            consumer_growth = ['AMZN', 'TSLA', 'NKE']
            consumer_value = ['WMT', 'TGT', 'KO']
            
            healthcare_growth = ['MRNA', 'REGN', 'VRTX']
            healthcare_value = ['JNJ', 'PFE', 'MRK']
            
            # Map sectors to stock lists
            sector_mapping = {
                'Technology': {
                    'growth': tech_growth,
                    'value': tech_value
                },
                'Financial Services': {
                    'growth': finance_growth,
                    'value': finance_value
                },
                'Consumer Cyclical': {
                    'growth': consumer_growth,
                    'value': consumer_value
                },
                'Healthcare': {
                    'growth': healthcare_growth,
                    'value': healthcare_value
                }
            }
            
            # Get the relevant stock lists for the sector
            sector_stocks = sector_mapping.get(sector, {})
            if sector_stocks:
                categories['growth']['stocks'] = [s for s in sector_stocks['growth'] if s != ticker][:2]
                categories['value']['stocks'] = [s for s in sector_stocks['value'] if s != ticker][:2]
                
                # Get basic info for each stock
                for category in categories.values():
                    stock_details = []
                    for symbol in category['stocks']:
                        try:
                            stock_info = yf.Ticker(symbol).info
                            stock_details.append({
                                'symbol': symbol,
                                'name': stock_info.get('shortName', symbol),
                                'price': stock_info.get('currentPrice', 0),
                                'change': stock_info.get('regularMarketChangePercent', 0)
                            })
                        except Exception as e:
                            print(f"Error getting info for {symbol}: {str(e)}")
                            continue
                    category['stocks'] = stock_details
                
                return {
                    'sector': sector,
                    'industry': industry,
                    'categories': categories
                }
            
            return None
            
        except Exception as e:
            print(f"Error finding similar stocks: {str(e)}")
            return None

    @staticmethod
    def get_competitors(ticker):
        """Get competitor information for the given ticker"""
        try:
            print(f"\nFetching competitor data for {ticker}")
            stock = yf.Ticker(ticker)
            
            # Get company info
            info = stock.info
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            company_revenue_growth = info.get('revenueGrowth', 0)
            company_profit_margin = info.get('profitMargins', 0)
            company_pe = info.get('trailingPE', 0)
            
            if not sector or not industry:
                print(f"No sector/industry data for {ticker}")
                return None
                
            print(f"Sector: {sector}, Industry: {industry}")
            
            # Predefined competitor mappings for specific industries
            industry_competitors = {
                'Aerospace & Defense': ['BA', 'LMT', 'RTX', 'NOC', 'SPCE', 'RKLB', 'ASTR'],
                'Semiconductors': ['NVDA', 'AMD', 'INTC', 'TSM', 'QCOM', 'MU'],
                'Software—Infrastructure': ['MSFT', 'ORCL', 'VMW', 'CTXS', 'NLOK'],
                'Internet Content & Information': ['GOOGL', 'META', 'PINS', 'SNAP', 'TWTR'],
                'Auto Manufacturers': ['TSLA', 'F', 'GM', 'TM', 'RIVN', 'NIO'],
                'Consumer Electronics': ['AAPL', 'SONY', 'BBY', 'SONO'],
                'Biotechnology': ['NBIX', 'BIIB', 'AMGN', 'GILD', 'VRTX', 'REGN']
            }
            
            # Get competitors from predefined list or Yahoo Finance
            competitors = []
            if industry in industry_competitors:
                competitors = [c for c in industry_competitors[industry] if c != ticker]
            
            # If no predefined competitors or less than 2 found, try to get from Yahoo Finance
            if len(competitors) < 2:
                try:
                    recom = stock.recommendations
                    if recom is not None:
                        similar_tickers = recom.index.get_level_values(1).unique().tolist()
                        competitors.extend([t for t in similar_tickers if t != ticker])
                except Exception as e:
                    print(f"Error getting recommendations: {e}")
            
            # Remove duplicates and limit to top 5
            competitors = list(dict.fromkeys(competitors))[:5]
            
            if not competitors:
                print(f"No competitors found for {ticker}")
                return None
            
            # Get detailed info for each competitor
            competitor_data = []
            total_revenue_growth = 0
            total_profit_margin = 0
            total_pe = 0
            valid_metrics = 0
            
            for comp_ticker in competitors:
                try:
                    comp = yf.Ticker(comp_ticker)
                    comp_info = comp.info
                    
                    # Get financial metrics
                    revenue_growth = comp_info.get('revenueGrowth', 0)
                    profit_margin = comp_info.get('profitMargins', 0)
                    pe_ratio = comp_info.get('trailingPE', 0)
                    
                    # Add to totals for averaging
                    if revenue_growth:
                        total_revenue_growth += revenue_growth
                    if profit_margin:
                        total_profit_margin += profit_margin
                    if pe_ratio:
                        total_pe += pe_ratio
                    if revenue_growth or profit_margin or pe_ratio:
                        valid_metrics += 1
                    
                    competitor_data.append({
                        'symbol': comp_ticker,
                        'name': comp_info.get('shortName', comp_ticker),
                        'price': comp_info.get('currentPrice', 0),
                        'market_cap': comp_info.get('marketCap', 0),
                        'revenue_growth': f"{revenue_growth*100:.1f}%" if revenue_growth else "N/A",
                        'profit_margin': f"{profit_margin*100:.1f}%" if profit_margin else "N/A",
                        'pe_ratio': f"{pe_ratio:.1f}" if pe_ratio else "N/A"
                    })
                except Exception as e:
                    print(f"Error getting data for competitor {comp_ticker}: {e}")
                    continue
            
            if not competitor_data:
                return None
            
            # Calculate averages for comparison
            avg_revenue_growth = total_revenue_growth / valid_metrics if valid_metrics > 0 else 0
            avg_profit_margin = total_profit_margin / valid_metrics if valid_metrics > 0 else 0
            avg_pe = total_pe / valid_metrics if valid_metrics > 0 else 0
            
            # Generate insights
            insights = []
            
            # Revenue Growth comparison
            if company_revenue_growth and avg_revenue_growth:
                if company_revenue_growth > avg_revenue_growth * 1.2:
                    insights.append(f"{ticker} shows superior revenue growth ({company_revenue_growth*100:.1f}%) compared to industry average ({avg_revenue_growth*100:.1f}%)")
                elif company_revenue_growth < avg_revenue_growth * 0.8:
                    insights.append(f"{ticker}'s revenue growth ({company_revenue_growth*100:.1f}%) is below industry average ({avg_revenue_growth*100:.1f}%)")
            
            # Profit Margin comparison
            if company_profit_margin and avg_profit_margin:
                if company_profit_margin > avg_profit_margin * 1.2:
                    insights.append(f"{ticker} demonstrates stronger profit margins ({company_profit_margin*100:.1f}%) versus industry average ({avg_profit_margin*100:.1f}%)")
                elif company_profit_margin < avg_profit_margin * 0.8:
                    insights.append(f"{ticker}'s profit margins ({company_profit_margin*100:.1f}%) lag behind industry average ({avg_profit_margin*100:.1f}%)")
            
            # PE Ratio comparison
            if company_pe and avg_pe:
                if company_pe > avg_pe * 1.2:
                    insights.append(f"{ticker} trades at a premium PE ratio ({company_pe:.1f}x) compared to industry average ({avg_pe:.1f}x)")
                elif company_pe < avg_pe * 0.8:
                    insights.append(f"{ticker} trades at a discount PE ratio ({company_pe:.1f}x) compared to industry average ({avg_pe:.1f}x)")
            
            return {
                'sector': sector,
                'industry': industry,
                'competitors': competitor_data,
                'competitor_insights': insights
            }
            
        except Exception as e:
            print(f"Error getting competitors for {ticker}: {e}")
            return None