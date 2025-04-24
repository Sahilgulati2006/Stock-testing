import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
from scipy.optimize import minimize
from app.stock_service import StockService
from app.postgres_storage_service import PostgresStorageService
from collections import defaultdict

class PortfolioService:
    def __init__(self):
        self.stock_service = StockService()
        self.storage_service = PostgresStorageService()
        
    def calculate_portfolio_metrics(self, portfolio_data):
        """Calculate key portfolio metrics"""
        try:
            if not portfolio_data.get('positions'):
                return {
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
                }

            total_value = 0.0
            total_cost = 0.0
            positions = []
            
            # Process each position
            for position in portfolio_data['positions']:
                try:
                    ticker = position['ticker']
                    shares = float(position['shares'])
                    cost_basis = float(position['cost_basis'])
                    total_cost += cost_basis * shares
                    
                    # Get current stock data
                    stock_data = self.stock_service.get_stock_data(ticker)
                    if stock_data is None or stock_data.empty:
                        continue
                        
                    current_price = float(stock_data['Close'].iloc[-1])
                    position_value = current_price * shares
                    
                    # Get stock info including sector
                    stock_info = self.stock_service.get_fundamentals(ticker)
                    sector = stock_info.get('sector', 'Unknown') if stock_info else 'Unknown'
                    
                    # Calculate position metrics
                    unrealized_gain = position_value - (cost_basis * shares)
                    unrealized_gain_pct = (unrealized_gain / (cost_basis * shares)) * 100 if cost_basis > 0 else 0.0
                    
                    # Calculate daily return
                    if len(stock_data) >= 2:
                        prev_price = float(stock_data['Close'].iloc[-2])
                        daily_return = ((current_price - prev_price) / prev_price) * 100
                    else:
                        daily_return = 0.0
                    
                    # Store position data
                    position_info = {
                        'ticker': ticker,
                        'shares': float(shares),
                        'cost_basis': float(cost_basis),
                        'current_price': float(current_price),
                        'position_value': float(position_value),
                        'unrealized_gain': float(unrealized_gain),
                        'unrealized_gain_pct': float(unrealized_gain_pct),
                        'daily_return': float(daily_return),
                        'sector': sector
                    }
                    
                    positions.append(position_info)
                    total_value += position_value
                except Exception as e:
                    print(f"Error processing position {position.get('ticker', 'unknown')}: {str(e)}")
                    continue
            
            if not positions:
                return {
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
                }
            
            # Calculate portfolio daily return as weighted average of position returns
            portfolio_daily_return = sum(
                p['daily_return'] * (p['position_value'] / total_value)
                for p in positions
            ) if total_value > 0 else 0.0
            
            # Calculate volatility using weighted daily returns
            weighted_returns = [
                p['daily_return'] * (p['position_value'] / total_value)
                for p in positions
            ] if total_value > 0 else [0.0]
            
            # Annualize volatility
            volatility = float(np.std(weighted_returns) * np.sqrt(252)) if len(weighted_returns) > 1 else 0.0
            
            # Calculate total portfolio growth
            total_growth = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0.0
            
            # Calculate simple beta
            try:
                spy_data = yf.download('^GSPC', start=(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'))
                if not spy_data.empty and len(spy_data) >= 2:
                    spy_current = float(spy_data['Close'].iloc[-1])
                    spy_prev = float(spy_data['Close'].iloc[-2])
                    spy_return = ((spy_current - spy_prev) / spy_prev) * 100
                    beta = float(portfolio_daily_return / spy_return) if spy_return != 0 else 1.0
                else:
                    beta = 1.0
            except Exception as e:
                print(f"Error calculating beta: {str(e)}")
                beta = 1.0
            
            # Calculate simple VaR
            var_95 = float(total_value * (2.33 * volatility / np.sqrt(252))) if volatility > 0 else 0.0
            
            return {
                'total_value': float(total_value),
                'positions': positions,
                'metrics': {
                    'daily_return': float(portfolio_daily_return),
                    'weekly_return': float(portfolio_daily_return * 5),  # Simple approximation
                    'monthly_return': float(portfolio_daily_return * 21),  # Simple approximation
                    'yearly_return': float(portfolio_daily_return * 252),  # Simple approximation
                    'volatility': float(volatility),
                    'total_growth': float(total_growth),
                    'beta': float(beta),
                    'var_95': float(var_95)
                }
            }
            
        except Exception as e:
            print(f"Error calculating portfolio metrics: {str(e)}")
            return {
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
            }
            
    def optimize_portfolio(self, portfolio_data, risk_tolerance='moderate'):
        """Optimize portfolio weights based on modern portfolio theory"""
        try:
            if not portfolio_data.get('positions'):
                return {
                    'tickers': [],
                    'current_weights': [],
                    'optimized_weights': [],
                    'expected_return': 0,
                    'expected_risk': 0,
                    'rebalancing_needed': False
                }

            returns_data = []
            tickers = []
            total_value = sum(float(p.get('position_value', 0)) for p in portfolio_data['positions'])
            
            if total_value == 0:
                return {
                    'tickers': [],
                    'current_weights': [],
                    'optimized_weights': [],
                    'expected_return': 0,
                    'expected_risk': 0,
                    'rebalancing_needed': False
                }
            
            current_weights = []
            
            # Get historical returns for each position
            for position in portfolio_data['positions']:
                ticker = position['ticker']
                position_value = float(position.get('position_value', 0))
                current_weight = position_value / total_value if total_value > 0 else 0
                current_weights.append(current_weight)
                
                stock_data = self.stock_service.get_stock_data(ticker)
                returns = stock_data['Close'].pct_change()
                returns_data.append(returns)
                tickers.append(ticker)
            
            if not tickers:
                return {
                    'tickers': [],
                    'current_weights': [],
                    'optimized_weights': [],
                    'expected_return': 0,
                    'expected_risk': 0,
                    'rebalancing_needed': False
                }
            
            # Create returns matrix
            returns_matrix = pd.concat(returns_data, axis=1)
            returns_matrix.columns = tickers
            
            # Calculate mean returns and covariance matrix
            mean_returns = returns_matrix.mean() * 252
            cov_matrix = returns_matrix.cov() * 252
            
            # Define risk tolerance parameters
            risk_params = {
                'conservative': {'target_return': 0.06, 'max_weight': 0.3},
                'moderate': {'target_return': 0.10, 'max_weight': 0.4},
                'aggressive': {'target_return': 0.15, 'max_weight': 0.5}
            }
            
            param = risk_params.get(risk_tolerance, risk_params['moderate'])
            
            # Define optimization constraints
            constraints = [
                {'type': 'eq', 'fun': lambda x: np.sum(x) - 1}  # weights sum to 1
            ]
            
            # Add constraint for maximum weight per position
            bounds = tuple((0, param['max_weight']) for _ in range(len(tickers)))
            
            # Define objective function (minimize portfolio variance)
            def objective(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            # Initial guess (equal weights)
            initial_weights = np.array([1/len(tickers)] * len(tickers))
            
            try:
                # Optimize
                result = minimize(objective, initial_weights, method='SLSQP', bounds=bounds, constraints=constraints)
                
                if result.success:
                    optimized_weights = result.x
                    return {
                        'tickers': tickers,
                        'current_weights': current_weights,
                        'optimized_weights': optimized_weights.tolist(),
                        'expected_return': param['target_return'] * 100,
                        'expected_risk': result.fun * 100,
                        'rebalancing_needed': any(abs(current - opt) > 0.05 
                                                for current, opt in zip(current_weights, optimized_weights))
                    }
            except Exception as e:
                print(f"Optimization calculation failed: {str(e)}")
            
            # If optimization fails, return current weights as optimal
            return {
                'tickers': tickers,
                'current_weights': current_weights,
                'optimized_weights': current_weights,
                'expected_return': 0,
                'expected_risk': 0,
                'rebalancing_needed': False
            }
            
        except Exception as e:
            print(f"Error in portfolio optimization: {str(e)}")
            return {
                'tickers': [],
                'current_weights': [],
                'optimized_weights': [],
                'expected_return': 0,
                'expected_risk': 0,
                'rebalancing_needed': False
            }
            
    def calculate_diversification_metrics(self, portfolio_data):
        """Calculate portfolio diversification metrics"""
        try:
            # Get sector and geographic data for each position
            sector_allocation = defaultdict(float)
            geo_allocation = defaultdict(float)
            
            for position in portfolio_data['positions']:
                ticker = position['ticker']
                weight = position['position_value'] / portfolio_data['total_value']
                
                # Get stock info
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Update sector allocation
                sector = info.get('sector', 'Unknown')
                sector_allocation[sector] += weight
                
                # Update geographic allocation
                country = info.get('country', 'Unknown')
                geo_allocation[country] += weight
                
            # Calculate Herfindahl-Hirschman Index (HHI) for concentration
            sector_hhi = sum(weight ** 2 for weight in sector_allocation.values())
            geo_hhi = sum(weight ** 2 for weight in geo_allocation.values())
            
            # Calculate diversification score (1 - HHI, normalized to 0-100)
            sector_diversity = (1 - sector_hhi) * 100
            geo_diversity = (1 - geo_hhi) * 100
            
            return {
                'sector_allocation': dict(sector_allocation),
                'geographic_allocation': dict(geo_allocation),
                'sector_diversity_score': sector_diversity,
                'geographic_diversity_score': geo_diversity,
                'overall_diversity_score': (sector_diversity + geo_diversity) / 2
            }
            
        except Exception as e:
            print(f"Error calculating diversification metrics: {str(e)}")
            raise 