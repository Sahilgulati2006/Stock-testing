import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

class MarketSentimentService:
    def __init__(self):
        self.vix_threshold = {'fear': 30, 'greed': 20}
        self.momentum_days = 125  # ~6 months of trading days
        
    def get_fear_greed_index(self):
        """
        Calculate Fear & Greed Index based on CNN's methodology:
        1. Market Momentum (S&P 500 vs 125-day MA) - 25%
        2. Market Volatility (VIX) - 25%
        3. Stock Price Breadth (% stocks above 50-day MA) - 25%
        4. Safe Haven Demand (Treasury Yield vs S&P dividend yield) - 25%
        
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
            
            # Get Treasury yield data
            tyx = yf.Ticker('^TNX')
            tyx_data = tyx.history(period='5d')
            treasury_yield = tyx_data['Close'].iloc[-1]
            
            # Calculate indicators
            momentum_score = self._calculate_momentum_score(sp500_data)
            vix_score = self._calculate_vix_score(current_vix)
            breadth_score = self._calculate_market_breadth()
            safe_haven_score = self._calculate_safe_haven_demand(treasury_yield, sp500_data)
            
            # Calculate final index (weighted average)
            weights = {
                'momentum': 0.25,
                'vix': 0.25,
                'breadth': 0.25,
                'safe_haven': 0.25
            }
            
            index_value = (
                momentum_score * weights['momentum'] +
                vix_score * weights['vix'] +
                breadth_score * weights['breadth'] +
                safe_haven_score * weights['safe_haven']
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
                    'momentum': round(momentum_score, 1),
                    'vix': round(vix_score, 1),
                    'breadth': round(breadth_score, 1),
                    'safe_haven': round(safe_haven_score, 1)
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
                    'momentum': 50,
                    'vix': 50,
                    'breadth': 50,
                    'safe_haven': 50
                }
            }
    
    def _calculate_vix_score(self, current_vix):
        """Convert VIX value to 0-100 score (inverse relationship)"""
        if current_vix >= 35:
            return 0  # Extreme fear
        elif current_vix <= 12:
            return 100  # Extreme greed
        
        # More sensitive scale for fear territory
        if current_vix > 25:
            # 25-35 range maps to 0-30 (fear territory)
            return max(0, 30 - ((current_vix - 25) * 3))
        else:
            # 12-25 range maps to 30-100 (neutral to greed territory)
            return min(100, 30 + ((25 - current_vix) * 5.4))
    
    def _calculate_momentum_score(self, sp500_data):
        """Calculate momentum score based on S&P 500 vs 125-day MA"""
        current_price = sp500_data['Close'].iloc[-1]
        sma_125 = sp500_data['Close'].rolling(window=self.momentum_days).mean().iloc[-1]
        
        # Calculate percentage difference from 125-day SMA
        pct_diff = ((current_price - sma_125) / sma_125) * 100
        
        # More sensitive to negative movements
        if pct_diff <= -7:
            return 0
        elif pct_diff >= 4:
            return 100
        else:
            # Map -7% to +4% range to 0-100 with higher sensitivity to negative moves
            return max(0, min(100, 50 + (pct_diff * 9)))
    
    def _calculate_market_breadth(self):
        """Calculate market breadth based on stocks above 50-day MA"""
        try:
            sp500 = yf.Ticker('^GSPC')
            components = sp500.history(period='60d')
            
            # Calculate 50-day MA
            ma_50 = components['Close'].rolling(window=50).mean()
            
            # Calculate percentage of stocks above 50-day MA
            stocks_above_ma = (components['Close'].iloc[-1] > ma_50.iloc[-1])
            breadth_pct = stocks_above_ma * 100
            
            # Convert to 0-100 score
            if breadth_pct <= 20:
                return 0
            elif breadth_pct >= 80:
                return 100
            else:
                return (breadth_pct - 20) * (100 / 60)  # Map 20-80 range to 0-100
                
        except Exception as e:
            print(f"Error calculating market breadth: {str(e)}")
            return 50  # Return neutral score on error
    
    def _calculate_safe_haven_demand(self, treasury_yield, sp500_data):
        """Calculate safe haven demand based on Treasury yield vs S&P dividend yield"""
        try:
            # Calculate S&P 500 dividend yield (approximate)
            annual_dividend = sp500_data['Close'].iloc[-1] * 0.015  # Approximate 1.5% dividend yield
            current_yield = (annual_dividend / sp500_data['Close'].iloc[-1]) * 100
            
            # Calculate spread between Treasury yield and S&P dividend yield
            spread = treasury_yield - current_yield
            
            # More sensitive spread ranges
            if spread <= -1.5:
                return 0  # Extreme fear (flight to safety)
            elif spread >= 1.5:
                return 100  # Extreme greed (risk-on)
            else:
                return 50 + (spread * 33.33)  # Map -1.5 to +1.5 range to 0-100
                
        except Exception as e:
            print(f"Error calculating safe haven demand: {str(e)}")
            return 50  # Return neutral score on error
    
    def _get_category_and_signals(self, index_value, vix, sp500_data):
        """Determine sentiment category and generate insight signals"""
        # Define category thresholds to match CNN's scale
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
            signals.append("High market volatility indicates extreme fear")
        elif vix < 15:
            signals.append("Low volatility suggests market complacency")
            
        # Momentum signals
        current_price = sp500_data['Close'].iloc[-1]
        sma_125 = sp500_data['Close'].rolling(window=self.momentum_days).mean().iloc[-1]
        pct_diff = ((current_price - sma_125) / sma_125) * 100
        
        if pct_diff < -5:
            signals.append("Market showing significant weakness")
        elif pct_diff < -2:
            signals.append("Market trading below average levels")
        elif pct_diff > 5:
            signals.append("Strong market momentum detected")
            
        return category, signals 