import praw
import re
from collections import defaultdict, Counter
from transformers import pipeline, AutoTokenizer
from datetime import date, datetime, timedelta
import pandas as pd
import os
from app.config import Config
import yfinance as yf

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
            # Common verbs and actions
            'MOVE', 'RUN', 'COST', 'TAX', 'CASH', 'PAY', 'PAID', 'ELSE', 'EVER', 'LINE', 'PLAN', 'PLAY',
            'STAY', 'TELL', 'THINK', 'NEED', 'LOOK', 'LIKE', 'HELP', 'WORK', 'CALL', 'TRY', 'ASK', 'SEEM',
            'FEEL', 'KEEP', 'LET', 'READ', 'SAY', 'SAID', 'SAYS', 'TALK', 'TURN', 'WANT', 'SHOW', 'HEAR',
            # Common nouns
            'CAR', 'LOT', 'WAY', 'LIFE', 'DAY', 'MAN', 'MEN', 'WOMAN', 'WOMEN', 'CHILD', 'NAME', 'FACT',
            'HOME', 'AIR', 'LINE', 'END', 'LOVE', 'HAND', 'HEAD', 'SIDE', 'EYE', 'MIND', 'DOOR', 'FACE',
            'CASE', 'EDGE', 'BANK', 'RISK', 'KIND', 'BODY', 'CARE', 'BOOK', 'FOOD', 'KIDS', 'TEAM',
            # Finance-related common words (when not referring to stocks)
            'CASH', 'COST', 'TAX', 'EARN', 'LOSS', 'DEBT', 'LOAN', 'RATE', 'FUND', 'BANK', 'SAVE',
            'DEAL', 'SALE', 'RENT', 'OWN', 'PAID', 'FREE', 'BILL', 'FEES', 'FINE', 'GAIN', 'LOST',
            # Technology and internet common words
            'POST', 'LINK', 'SITE', 'PAGE', 'USER', 'DATA', 'FILE', 'CODE', 'APPS', 'TECH', 'WEB',
            # Measurements and units
            'HIGH', 'LOW', 'BIG', 'TOP', 'DOWN', 'OVER', 'MORE', 'LESS', 'MANY', 'MUCH', 'FULL',
            'HALF', 'PART', 'LATE', 'LONG', 'FAR', 'DEEP', 'FAST', 'SLOW', 'HARD', 'SOFT', 'HOT',
            'COLD', 'WARM', 'COOL', 'SAFE', 'RICH', 'POOR', 'GOOD', 'BAD'
        }
        
        # Stock-related context words that increase confidence
        self.stock_context = {
            'stock', 'share', 'shares', 'ticker', '$', 'trading', 'price', 'market', 'buy', 'sell',
            'bullish', 'bearish', 'calls', 'puts', 'position', 'holding', 'portfolio', 'investor',
            'investing', 'earnings', 'dividend', 'dividends', 'etf', 'stonk', 'stonks', 'yolo',
            'short', 'shorted', 'shorting', 'long', 'margin', 'options', 'call', 'put', 'strike',
            'expiry', 'itm', 'otm', 'hedge', 'resistance', 'support', 'technical', 'fundamental',
            'analysis', 'chart', 'breakout', 'squeeze', 'volume', 'volatility', 'market cap'
        }
        
        # Cache for validated tickers
        self.validated_tickers = {}
    
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
        
        # First check for strong stock indicators
        strong_indicators = [
            rf'\${ticker}\b',  # $TICKER
            rf'\b{ticker}(?:\s+(?:stock|share|call|put|option)s?\b)',  # TICKER stock/share/call/put
            rf'(?:buy|sell|short|long)\s+\b{ticker}\b',  # buy/sell/short/long TICKER
            rf'\b{ticker}\s+(?:earnings|dividend|squeeze|breakout|analysis)\b',  # TICKER earnings/dividend/etc
            rf'(?:bullish|bearish)\s+(?:on\s+)?\b{ticker}\b',  # bullish/bearish on TICKER
        ]
        
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in strong_indicators):
            return True
            
        # Check for company name mentions with stock context
        company_name = self.tickers_data[ticker]
        company_patterns = [
            rf'{company_name}.*?(?:stock|share|price|market|trading)',
            rf'(?:stock|share|price|market|trading).*?{company_name}'
        ]
        
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in company_patterns):
            return True
            
        # Count stock-related context words in the vicinity of the ticker
        context_window = 50  # characters before and after
        ticker_pos = text_lower.find(ticker.lower())
        if ticker_pos != -1:
            start = max(0, ticker_pos - context_window)
            end = min(len(text_lower), ticker_pos + len(ticker) + context_window)
            context_text = text_lower[start:end]
            
            context_word_count = sum(1 for word in self.stock_context if word in context_text)
            if context_word_count >= 2:  # Require at least 2 context words
                return True
        
        return False
    
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
    
    def is_valid_ticker(self, symbol):
        """
        Check if a symbol is a valid stock ticker by attempting to get its info from yfinance.
        Caches results to avoid repeated API calls.
        """
        if symbol in self.validated_tickers:
            return self.validated_tickers[symbol]
        
        try:
            # Skip validation for common non-stock words
            if symbol in self.exclude_words:
                self.validated_tickers[symbol] = False
                return False

            # Try to get stock info
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # Check if it's a valid stock by verifying essential fields
            is_valid = bool(
                info.get('symbol') and  # Must have a symbol
                info.get('regularMarketPrice') and  # Must have a price
                info.get('quoteType') in ['EQUITY', 'ETF']  # Must be a stock or ETF
            )
            
            self.validated_tickers[symbol] = is_valid
            return is_valid
            
        except Exception:
            self.validated_tickers[symbol] = False
            return False

    def extract_tickers(self, text):
        """Extract stock tickers from text and validate them"""
        # Pattern for stock tickers: $TICKER or just TICKER (all caps, 1-5 characters)
        pattern = r'\$?([A-Z]{1,5})\b'
        matches = re.findall(pattern, text)
        
        # Filter out common words and validate tickers
        valid_tickers = [ticker for ticker in matches if self.is_valid_ticker(ticker)]
        return valid_tickers
    
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