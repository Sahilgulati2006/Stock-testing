import praw
import re
from collections import defaultdict, Counter
from transformers import pipeline, AutoTokenizer
from datetime import date, datetime, timedelta
import pandas as pd
import os
from app.config import Config

# Initialize sentiment analyzer
sentiment_analyzer = pipeline("sentiment-analysis", model=Config.SENTIMENT_MODEL)
tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")

class SentimentService:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent="stock_analysis_app/1.0"
        )
        
        # Load NASDAQ tickers and company names
        self.tickers_data = self._load_nasdaq_tickers()
        self.tickers_nasdaq = set(self.tickers_data.keys())
        
        # Common words and patterns to exclude
        self.exclude_words = {
            # Common English words that might be mistaken for tickers
            'A', 'I', 'ME', 'MY', 'UP', 'ON', 'IN', 'AT', 'TO', 'IS', 'IT', 'BE', 'BY', 'GO', 'IF', 'DO',
            'AM', 'AN', 'AS', 'SO', 'OR', 'AND', 'BUT', 'OUT', 'NOW', 'NEW', 'WAY', 'WHO', 'WHY', 'GOOD',
            'BAD', 'BIG', 'ALL', 'ANY', 'CAN', 'DAY', 'GET', 'HAS', 'HAD', 'HOW', 'ONE', 'OUR', 'SEE',
            'THE', 'TWO', 'WAS', 'YOU', 'YES', 'NO', 'NOT', 'OFF', 'TOO', 'USE', 'USA', 'UK', 'EU',
            'NEXT', 'LAST', 'BACK', 'WELL', 'JUST', 'MAKE', 'MADE', 'MANY', 'TAKE', 'TOOK', 'VERY',
            'REAL', 'SAME', 'SOME', 'TIME', 'TRUE', 'WHAT', 'WHEN', 'WILL', 'WITH', 'YEAR', 'WANT',
            # Add more common words as needed
        }
        
        # Stock-related context words that increase confidence
        self.stock_context = {
            'stock', 'share', 'shares', 'ticker', '$', 'trading', 'price', 'market', 'buy', 'sell',
            'bullish', 'bearish', 'calls', 'puts', 'position', 'holding', 'portfolio', 'investor',
            'investing', 'earnings', 'dividend', 'dividends', 'etf', 'stonk', 'stonks', 'yolo'
        }
    
    def _load_nasdaq_tickers(self):
        """Load NASDAQ tickers and company names from CSV"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        nasdaq_path = os.path.join(current_dir, 'nasdaq-listed.csv')
        df = pd.read_csv(nasdaq_path)
        
        # Create a dictionary of tickers to company names
        tickers_dict = {}
        for _, row in df.iterrows():
            ticker = str(row['Symbol']).strip()
            name = str(row['Security Name']).strip()
            if pd.notna(ticker) and pd.notna(name):
                tickers_dict[ticker] = name
                
        return tickers_dict
    
    def _split_text_into_chunks(self, text, max_length=510):
        """Split text for sentiment analysis"""
        tokenized_text = tokenizer.encode(text, truncation=True, max_length=max_length)
        return [tokenizer.decode(tokenized_text[i:i+max_length]) 
                for i in range(0, len(tokenized_text), max_length)]
    
    def _has_stock_context(self, text, ticker):
        """Check if the ticker appears in a stock-related context"""
        text_lower = text.lower()
        
        # Check for stock-related context words
        if any(context in text_lower for context in self.stock_context):
            return True
            
        # Check for common stock mention patterns
        patterns = [
            rf'\${ticker}',  # $TICKER
            rf'(?:^|\s){ticker}(?:\s|$)',  # TICKER as a word
            rf'(?:^|\s){ticker.lower()}(?:\s|$)',  # ticker as a word
            rf'(?:^|\s){self.tickers_data[ticker]}(?:\s|$)',  # Company name
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    
    def _extract_stock_mentions(self, text):
        """Extract stock tickers from text with improved accuracy"""
        # Convert text to uppercase for matching
        text_upper = text.upper()
        
        # Find all potential stock mentions (1-5 capital letters)
        potential_mentions = re.findall(r'\b[A-Z]{1,5}\b|\$[A-Z]{1,5}\b', text_upper)
        
        # Clean potential mentions
        potential_mentions = [m.strip('$') for m in potential_mentions]
        
        # Filter out common words and validate against NASDAQ tickers
        valid_mentions = []
        for mention in potential_mentions:
            if (mention in self.tickers_nasdaq and 
                mention not in self.exclude_words and 
                self._has_stock_context(text, mention)):
                valid_mentions.append(mention)
        
        return valid_mentions
    
    def analyze_subreddit(self, subreddit_name="wallstreetbets"):
        """Analyze stock mentions and sentiment in a subreddit"""
        print(f"\nAnalyzing r/{subreddit_name}...")
        
        subreddit = self.reddit.subreddit(subreddit_name)
        
        # Get posts from the last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Get hot posts
        hot_posts = subreddit.hot(limit=Config.MAX_REDDIT_POSTS)
        
        tickers_reddit = []
        stock_sentiments = defaultdict(list)
        
        for post in hot_posts:
            # Skip posts older than 24 hours
            if datetime.fromtimestamp(post.created_utc) < cutoff_time:
                continue
                
            print(f"\nProcessing post: {post.title[:50]}...")
            
            # Process post title and body
            full_text = f"{post.title.strip()} {post.selftext.strip() if post.selftext else ''}"
            
            if full_text:
                # Extract stock mentions
                mentions = self._analyze_text(full_text)
                tickers_reddit.extend(mentions)
                
                # Analyze sentiment
                chunks = self._split_text_into_chunks(full_text)
                sentiments = [sentiment_analyzer(chunk)[0]['label'] for chunk in chunks]
                
                for ticker in mentions:
                    stock_sentiments[ticker].extend(sentiments)
            
            # Process comments
            print("Processing comments...")
            post.comments.replace_more(limit=0)
            for comment in post.comments.list():
                # Skip comments older than 24 hours
                if datetime.fromtimestamp(comment.created_utc) < cutoff_time:
                    continue
                    
                comment_text = comment.body.strip()
                if comment_text:
                    # Extract stock mentions
                    mentions = self._analyze_text(comment_text)
                    tickers_reddit.extend(mentions)
                    
                    # Analyze sentiment
                    chunks = self._split_text_into_chunks(comment_text)
                    sentiments = [sentiment_analyzer(chunk)[0]['label'] for chunk in chunks]
                    
                    for ticker in mentions:
                        stock_sentiments[ticker].extend(sentiments)
        
        # Count mentions and analyze sentiment
        top_stocks = Counter(tickers_reddit).most_common(10)
        
        sentiment_results = {}
        for stock, sentiments in stock_sentiments.items():
            positive = sentiments.count("POSITIVE")
            negative = sentiments.count("NEGATIVE")
            
            if positive > negative:
                overall = "Bullish 📈"
            elif negative > positive:
                overall = "Bearish 📉"
            else:
                overall = "Neutral ⚖️"
            
            sentiment_results[stock] = {
                "positive": positive,
                "negative": negative,
                "total": len(sentiments),
                "sentiment": overall
            }
        
        print(f"\nAnalysis complete. Found {len(top_stocks)} top stocks.")
        return {
            "date": date.today(),
            "subreddit": subreddit_name,
            "top_stocks": top_stocks,
            "sentiment_results": sentiment_results
        }
    
    def _analyze_text(self, text):
        """Analyze text for stock mentions"""
        mentions = self._extract_stock_mentions(text)
        return mentions