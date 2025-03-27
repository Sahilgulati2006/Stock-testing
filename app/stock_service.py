import yfinance as yf
from datetime import date, timedelta
import pandas as pd
from polygon import RESTClient
from config import Config

client = RESTClient(Config.POLYGON_API_KEY)

class StockService:
    @staticmethod
    def get_stock_data(ticker, start_date="2023-01-01", end_date=date.today()):
        """Fetch historical stock data"""
        return yf.download(ticker, start=start_date, end=end_date)
    
    @staticmethod
    def calculate_technical_indicators(data):
        """Calculate EMA, RSI, etc."""
        # EMA calculations
        data['EMA_10'] = data['Close'].ewm(span=10, adjust=False).mean()
        data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
        data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
        data['EMA_100'] = data['Close'].ewm(span=100, adjust=False).mean()
        
        # RSI calculation
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        
        return data
    
    @staticmethod
    def calculate_fibonacci_levels(data):
        """Calculate Fibonacci retracement levels"""
        high = data['Close'].max()
        low = data['Close'].min()
        diff = high - low
        
        return {
            "0%": high,
            "23.6%": high - (0.236 * diff),
            "38.2%": high - (0.382 * diff),
            "50%": high - (0.5 * diff),
            "61.8%": high - (0.618 * diff),
            "100%": low,
        }
    
    @staticmethod
    def get_stock_news(ticker, limit=10):
        """Fetch recent news for a stock"""
        news = client.list_ticker_news(ticker, limit=limit)
        return [{
            "title": item.title,
            "description": item.description,
            "published": item.published_utc,
            "url": item.url
        } for item in news]
    
    @staticmethod
    def get_fundamentals(ticker):
        """Fetch fundamental data"""
        try:
            details = client.get_ticker_details(ticker)
            return {
                "name": details.name,
                "industry": details.sic_description,
                "market_cap": details.market_cap,
                "description": details.description
            }
        except Exception as e:
            print(f"Error fetching fundamentals: {e}")
            return None