import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

class PostgresStorageService:
    def __init__(self):
        load_dotenv()
        self.conn = self._get_connection()
        self._init_db()
    
    def _get_connection(self):
        """Create and return a database connection"""
        return psycopg2.connect(
            dbname=os.getenv('POSTGRES_DB', 'stock_portfolio'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'postgres'),
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=os.getenv('POSTGRES_PORT', '5432')
        )
    
    def _init_db(self):
        """Initialize database tables if they don't exist"""
        with self.conn.cursor() as cur:
            # Create portfolios table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolios (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    name VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create positions table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id SERIAL PRIMARY KEY,
                    portfolio_id INTEGER REFERENCES portfolios(id),
                    ticker VARCHAR(10) NOT NULL,
                    shares DECIMAL(15,2) NOT NULL,
                    cost_basis DECIMAL(15,2) NOT NULL,
                    purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create portfolio_history table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_history (
                    id SERIAL PRIMARY KEY,
                    portfolio_id INTEGER REFERENCES portfolios(id),
                    total_value DECIMAL(15,2) NOT NULL,
                    cash DECIMAL(15,2) NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Ensure we have at least one portfolio
            cur.execute("""
                INSERT INTO portfolios (user_id, name)
                SELECT 1, 'Default Portfolio'
                WHERE NOT EXISTS (SELECT 1 FROM portfolios LIMIT 1)
            """)
            
            self.conn.commit()
    
    def save_portfolio(self, portfolio_data):
        """Save portfolio data to PostgreSQL"""
        try:
            with self.conn.cursor() as cur:
                # Get the default portfolio
                cur.execute("SELECT id FROM portfolios ORDER BY id LIMIT 1")
                portfolio_id = cur.fetchone()[0]
                
                # Clear existing positions for this portfolio
                cur.execute("DELETE FROM positions WHERE portfolio_id = %s", (portfolio_id,))
                
                # Insert new positions
                for position in portfolio_data.get('positions', []):
                    cur.execute("""
                        INSERT INTO positions (
                            portfolio_id, ticker, shares, cost_basis, 
                            purchase_date, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        portfolio_id,
                        position['ticker'],
                        float(position['shares']),
                        float(position['cost_basis']),
                        datetime.now(),
                        datetime.now(),
                        datetime.now()
                    ))
                
                # Record portfolio history
                total_value = sum(
                    float(p.get('position_value', 0)) 
                    for p in portfolio_data.get('positions', [])
                ) + float(portfolio_data.get('cash', 0.0))
                
                cur.execute("""
                    INSERT INTO portfolio_history (portfolio_id, total_value, cash)
                    VALUES (%s, %s, %s)
                """, (portfolio_id, total_value, float(portfolio_data.get('cash', 0.0))))
                
                # Update portfolio last updated timestamp
                cur.execute("""
                    UPDATE portfolios 
                    SET updated_at = %s 
                    WHERE id = %s
                """, (datetime.now(), portfolio_id))
                
                self.conn.commit()
                return True
                
        except Exception as e:
            print(f"Error saving portfolio data: {str(e)}")
            self.conn.rollback()
            return False
    
    def load_portfolio(self):
        """Load portfolio data from PostgreSQL"""
        try:
            with self.conn.cursor() as cur:
                # Get the default portfolio
                cur.execute("""
                    SELECT id, updated_at
                    FROM portfolios
                    ORDER BY id LIMIT 1
                """)
                portfolio_row = cur.fetchone()
                
                if not portfolio_row:
                    return {'positions': [], 'cash': 0.0}
                
                portfolio_id, last_updated = portfolio_row
                
                # Get positions
                cur.execute("""
                    SELECT ticker, shares, cost_basis
                    FROM positions
                    WHERE portfolio_id = %s
                """, (portfolio_id,))
                
                positions = []
                for row in cur.fetchall():
                    positions.append({
                        'ticker': row[0],
                        'shares': float(row[1]),
                        'cost_basis': float(row[2])
                    })
                
                # Get latest cash value from history
                cur.execute("""
                    SELECT cash
                    FROM portfolio_history
                    WHERE portfolio_id = %s
                    ORDER BY recorded_at DESC
                    LIMIT 1
                """, (portfolio_id,))
                
                cash_row = cur.fetchone()
                cash = float(cash_row[0]) if cash_row else 0.0
                
                return {
                    'positions': positions,
                    'cash': cash,
                    'last_updated': last_updated.isoformat()
                }
                
        except Exception as e:
            print(f"Error loading portfolio data: {str(e)}")
            return {'positions': [], 'cash': 0.0}
    
    def get_portfolio_history(self, days=30):
        """Get portfolio history for the specified number of days"""
        try:
            with self.conn.cursor() as cur:
                # Get the default portfolio
                cur.execute("SELECT id FROM portfolios ORDER BY id LIMIT 1")
                portfolio_id = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT total_value, cash, recorded_at
                    FROM portfolio_history
                    WHERE portfolio_id = %s
                    AND recorded_at >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY recorded_at ASC
                """, (portfolio_id, days))
                
                history = []
                for row in cur.fetchall():
                    history.append({
                        'total_value': float(row[0]),
                        'cash': float(row[1]),
                        'recorded_at': row[2].isoformat()
                    })
                
                return history
                
        except Exception as e:
            print(f"Error getting portfolio history: {str(e)}")
            return []
    
    def reset_portfolio(self):
        """Reset the portfolio by removing all positions and history"""
        try:
            with self.conn.cursor() as cur:
                # Get the default portfolio
                cur.execute("SELECT id FROM portfolios ORDER BY id LIMIT 1")
                portfolio_id = cur.fetchone()[0]
                
                # Delete all positions for this portfolio
                cur.execute("DELETE FROM positions WHERE portfolio_id = %s", (portfolio_id,))
                
                # Delete portfolio history
                cur.execute("DELETE FROM portfolio_history WHERE portfolio_id = %s", (portfolio_id,))
                
                # Update portfolio last updated timestamp
                cur.execute("""
                    UPDATE portfolios 
                    SET updated_at = %s 
                    WHERE id = %s
                """, (datetime.now(), portfolio_id))
                
                self.conn.commit()
                return True
                
        except Exception as e:
            print(f"Error resetting portfolio: {str(e)}")
            self.conn.rollback()
            return False
    
    def __del__(self):
        """Close database connection when object is destroyed"""
        if hasattr(self, 'conn'):
            self.conn.close() 