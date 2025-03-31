import json
import os
from datetime import datetime

class StorageService:
    def __init__(self):
        self.storage_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.portfolio_file = os.path.join(self.storage_dir, 'portfolio.json')
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self):
        """Ensure the storage directory and files exist"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)
        if not os.path.exists(self.portfolio_file):
            self.save_portfolio({'positions': [], 'cash': 0.0})
    
    def save_portfolio(self, portfolio_data):
        """Save portfolio data to JSON file"""
        try:
            # Add timestamp for tracking last update
            portfolio_data['last_updated'] = datetime.now().isoformat()
            with open(self.portfolio_file, 'w') as f:
                json.dump(portfolio_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving portfolio data: {str(e)}")
            return False
    
    def load_portfolio(self):
        """Load portfolio data from JSON file"""
        try:
            with open(self.portfolio_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading portfolio data: {str(e)}")
            return {'positions': [], 'cash': 0.0} 