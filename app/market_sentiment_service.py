import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

class MarketSentimentService:
    def __init__(self):
        self.vix_threshold = {'fear': 30, 'greed': 20}
        self.momentum_days = 125  # ~6 months of trading days
        
    def get_fear_greed_index(self):
        """
        Calculate Fear & Greed Index based on multiple indicators:
        1. VIX (Volatility)
        2. Market Momentum (S&P 500)
        3. Market Volume
        4. Put/Call Ratio (using VIX as proxy)
        
        Returns:
        - dict with index value (0-100) and category
        """
        try:
            # Get VIX data
            vix = yf.Ticker('^VIX')
            vix_data = vix.history(period='5d')
            current_vix = vix_data['Close'].iloc[-1]
            
            # Get S&P 500 data
            sp500 = yf.Ticker('^GSPC')
            sp500_data = sp500.history(period=f'{self.momentum_days}d')
            
            # Calculate indicators
            vix_score = self._calculate_vix_score(current_vix)
            momentum_score = self._calculate_momentum_score(sp500_data)
            volume_score = self._calculate_volume_score(sp500_data)
            
            # Calculate final index (weighted average)
            weights = {
                'vix': 0.35,
                'momentum': 0.35,
                'volume': 0.30
            }
            
            index_value = (
                vix_score * weights['vix'] +
                momentum_score * weights['momentum'] +
                volume_score * weights['volume']
            )
            
            # Get category and signals
            category, signals = self._get_category_and_signals(
                index_value, 
                current_vix,
                sp500_data
            )
            
            return {
                'value': round(index_value, 1),
                'category': category,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'signals': signals,
                'indicators': {
                    'vix': round(vix_score, 1),
                    'momentum': round(momentum_score, 1),
                    'volume': round(volume_score, 1)
                }
            }
            
        except Exception as e:
            print(f"Error calculating Fear & Greed Index: {str(e)}")
            return {
                'value': 50,
                'category': 'Neutral',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'signals': ['Market sentiment data temporarily unavailable'],
                'indicators': {
                    'vix': 50,
                    'momentum': 50,
                    'volume': 50
                }
            }
    
    def _calculate_vix_score(self, current_vix):
        """Convert VIX value to 0-100 score (inverse relationship)"""
        if current_vix >= 40:
            return 0  # Extreme fear
        elif current_vix <= 10:
            return 100  # Extreme greed
        
        # Linear interpolation between ranges
        if current_vix > 25:
            return 50 - ((current_vix - 25) * 2)  # 25-40 maps to 50-0
        else:
            return 50 + ((25 - current_vix) * 2)  # 10-25 maps to 100-50
    
    def _calculate_momentum_score(self, sp500_data):
        """Calculate momentum score based on S&P 500 performance"""
        current_price = sp500_data['Close'].iloc[-1]
        sma_125 = sp500_data['Close'].rolling(window=self.momentum_days).mean().iloc[-1]
        
        # Calculate percentage difference from 125-day SMA
        pct_diff = ((current_price - sma_125) / sma_125) * 100
        
        # Convert to 0-100 score
        if pct_diff <= -10:
            return 0
        elif pct_diff >= 10:
            return 100
        else:
            return 50 + (pct_diff * 5)  # Scale -10% to +10% to 0-100
    
    def _calculate_volume_score(self, sp500_data):
        """Calculate volume score based on recent trading volume"""
        current_volume = sp500_data['Volume'].iloc[-5:].mean()  # 5-day average
        prev_volume = sp500_data['Volume'].iloc[-20:-5].mean()  # Previous 15 days
        
        volume_change = ((current_volume - prev_volume) / prev_volume) * 100
        
        # Convert to 0-100 score
        if volume_change <= -20:
            return 0
        elif volume_change >= 20:
            return 100
        else:
            return 50 + (volume_change * 2.5)  # Scale -20% to +20% to 0-100
    
    def _get_category_and_signals(self, index_value, vix, sp500_data):
        """Determine sentiment category and generate insight signals"""
        # Define category thresholds
        categories = {
            (0, 25): 'Extreme Fear',
            (25, 45): 'Fear',
            (45, 55): 'Neutral',
            (55, 75): 'Greed',
            (75, 100): 'Extreme Greed'
        }
        
        # Get category
        category = next(
            (cat for (low, high), cat in categories.items() 
             if low <= index_value <= high),
            'Neutral'
        )
        
        # Generate signals
        signals = []
        
        # VIX signals
        if vix > 35:
            signals.append("High VIX indicates extreme market fear")
        elif vix < 15:
            signals.append("Low VIX suggests market complacency")
            
        # Momentum signals
        current_price = sp500_data['Close'].iloc[-1]
        sma_125 = sp500_data['Close'].rolling(window=self.momentum_days).mean().iloc[-1]
        pct_diff = ((current_price - sma_125) / sma_125) * 100
        
        if pct_diff > 5:
            signals.append("Market showing strong upward momentum")
        elif pct_diff < -5:
            signals.append("Market showing significant weakness")
            
        # Volume signals
        current_volume = sp500_data['Volume'].iloc[-5:].mean()
        prev_volume = sp500_data['Volume'].iloc[-20:-5].mean()
        volume_change = ((current_volume - prev_volume) / prev_volume) * 100
        
        if volume_change > 15:
            signals.append("Unusually high trading volume detected")
        elif volume_change < -15:
            signals.append("Trading volume below normal levels")
            
        return category, signals 