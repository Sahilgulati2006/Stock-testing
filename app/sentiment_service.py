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
            'COLD', 'WARM', 'COOL', 'SAFE', 'RICH', 'POOR', 'GOOD', 'BAD', 'NICE', 'BEAT', 'BULL',
            # Reddit and internet specific terms
            'OP', 'IMG', 'OPEN', 'HOPE', 'HIT', 'EDIT', 'MOD', 'MODS', 'NSFW', 'TIL', 'TL', 'DR',
            'ELI5', 'PSA', 'AMA', 'IMO', 'IMHO', 'FOMO', 'YOLO', 'FUD', 'DD', 'DM', 'PM', 'TBA',
            'FAQ', 'IAMA', 'ETC', 'FYI', 'FTFY', 'IIRC', 'IRL', 'LOL', 'LMAO', 'AFAIK', 'NGL',
            'IDK', 'IKR', 'IMO', 'TBH', 'TLDR', 'WTF', 'BTW', 'AKA', 'NVM', 'ASAP', 'FWIW',
            'ICYMI', 'IIRC', 'IME', 'ITT', 'MFW', 'MRW', 'NSFL', 'OFC', 'OOC', 'OOL', 'OT',
            'POV', 'SMH', 'TFW', 'TIL', 'YSK', 'TIFU', 'AITA', 'CMV', 'DAE', 'ELI5', 'IANAL',
            'IFF', 'IWTL', 'JAQ', 'MFA', 'MMW', 'OOT', 'QED', 'RES', 'RIP', 'SRS', 'TRP',
            'UNBGBBIIVCHIDCTIICBG', 'WCGW', 'WIBTA', 'YTA', 'NTA', 'ESH', 'NAH', 'INFO'
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
        ticker_lower = ticker.lower()
        
        # First check for strong stock indicators
        strong_indicators = [
            rf'\${ticker}\b',  # $TICKER
            rf'\b{ticker}(?:\s+(?:stock|share|call|put|option)s?\b)',  # TICKER stock/share/call/put
            rf'(?:buy|sell|short|long)\s+\b{ticker}\b',  # buy/sell/short/long TICKER
            rf'\b{ticker}\s+(?:earnings|dividend|squeeze|breakout|analysis)\b',  # TICKER earnings/dividend/etc
            rf'(?:bullish|bearish)\s+(?:on\s+)?\b{ticker}\b',  # bullish/bearish on TICKER
            rf'(?:position|holding)s?\s+(?:in\s+)?\b{ticker}\b',  # position(s)/holding(s) in TICKER
            rf'\b{ticker}\s+(?:to the moon|mooning|dump|pump)',  # Common trading expressions
            rf'(?:calls|puts)\s+(?:on\s+)?\b{ticker}\b',  # calls/puts on TICKER
        ]
        
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in strong_indicators):
            return True
        
        # Check for company name mentions with stock context
        if ticker in self.tickers_data:
            company_name = self.tickers_data[ticker].lower()
            company_words = company_name.split()
            
            # Only proceed with company name check if the name is meaningful
            if len(company_words) > 1:  # Skip single-word company names as they might be too generic
                company_patterns = [
                    rf'{company_name}.*?(?:stock|share|price|market|trading)',
                    rf'(?:stock|share|price|market|trading).*?{company_name}'
                ]
                
                if any(re.search(pattern, text_lower) for pattern in company_patterns):
                    return True
        
        # Count stock-related context words in the vicinity of the ticker
        context_window = 100  # Increased window size
        ticker_positions = [m.start() for m in re.finditer(rf'\b{ticker_lower}\b', text_lower)]
        
        for pos in ticker_positions:
            start = max(0, pos - context_window)
            end = min(len(text_lower), pos + len(ticker_lower) + context_window)
            context_text = text_lower[start:end]
            
            # Count unique context words
            context_word_count = len({word for word in self.stock_context if word in context_text})
            
            # Require more context words for shorter tickers (which are more likely to be false positives)
            required_context_words = 3 if len(ticker) <= 2 else 2
            
            if context_word_count >= required_context_words:
                return True
        
        return False
    
    def _batch_validate_tickers(self, symbols):
        """
        Validate multiple stock tickers in a single batch to reduce API calls.
        Returns a dictionary of {symbol: is_valid} results.
        """
        # Filter out already validated tickers
        to_validate = [s for s in symbols if s not in self.validated_tickers]
        
        if not to_validate:
            return {s: self.validated_tickers[s] for s in symbols}
            
        try:
            # Create a single string of tickers joined by spaces
            ticker_string = " ".join(to_validate)
            tickers = yf.Tickers(ticker_string)
            
            results = {}
            for symbol in to_validate:
                try:
                    info = tickers.tickers[symbol].info if symbol in tickers.tickers else {}
                    
                    # Apply validation checks
                    is_valid = bool(
                        info.get('symbol') and
                        info.get('regularMarketPrice') and
                        info.get('quoteType') in ['EQUITY', 'ETF'] and
                        info.get('market') in ['us_market', 'nasdaq_market'] and
                        not info.get('delistedFromExchange', False)
                    )
                except:
                    is_valid = False
                    
                self.validated_tickers[symbol] = is_valid
                results[symbol] = is_valid
                
            return results
                
        except Exception:
            # If batch request fails, mark all as invalid
            for symbol in to_validate:
                self.validated_tickers[symbol] = False
            return {s: False for s in to_validate}

    def _extract_stock_mentions(self, text):
        """Extract stock tickers from text with improved accuracy"""
        # Convert text to uppercase for matching
        text_upper = text.upper()
        
        # Find all potential stock mentions (1-5 capital letters, with optional $ prefix)
        potential_mentions = re.findall(r'(?:^|\s)\$?([A-Z]{1,5})\b', text_upper)
        
        # Clean potential mentions
        potential_mentions = [m.strip('$') for m in potential_mentions]
        
        # Initial filtering
        filtered_mentions = [
            mention for mention in potential_mentions
            if (mention in self.tickers_nasdaq and 
                mention not in self.exclude_words and 
                len(mention) > 1)  # Exclude single-letter tickers
        ]
        
        # Get stock context for all mentions first
        context_valid_mentions = [
            mention for mention in filtered_mentions
            if self._has_stock_context(text, mention)
        ]
        
        # Batch validate all context-valid mentions at once
        if context_valid_mentions:
            valid_results = self._batch_validate_tickers(context_valid_mentions)
            return [ticker for ticker in context_valid_mentions if valid_results.get(ticker, False)]
        
        return []
    
    def is_valid_ticker(self, symbol):
        """
        Check if a symbol is a valid stock ticker using cached results or batch validation.
        """
        if symbol in self.validated_tickers:
            return self.validated_tickers[symbol]
        
        # Basic validation first
        if symbol in self.exclude_words or len(symbol) <= 1 or symbol not in self.tickers_nasdaq:
            self.validated_tickers[symbol] = False
            return False
            
        # Use batch validation even for single symbol
        results = self._batch_validate_tickers([symbol])
        return results.get(symbol, False)

    def extract_tickers(self, text):
        """Alias for _extract_stock_mentions for backward compatibility"""
        return self._extract_stock_mentions(text)
    
    def analyze_subreddit(self, subreddit_name="wallstreetbets", timeframe="day"):
        """Analyze stock mentions and sentiment in a subreddit"""
        print(f"\nAnalyzing r/{subreddit_name}...")
        
        subreddit = self.reddit.subreddit(subreddit_name)
        
        # Calculate cutoff time based on timeframe
        now = datetime.utcnow()
        cutoff_time = now
        if timeframe == "hour":
            cutoff_time = now - timedelta(hours=1)
        elif timeframe == "day":
            cutoff_time = now - timedelta(hours=24)
        elif timeframe == "week":
            cutoff_time = now - timedelta(days=7)
        elif timeframe == "month":
            cutoff_time = now - timedelta(days=30)
        elif timeframe == "year":
            cutoff_time = now - timedelta(days=365)
        # For "all" timeframe, we don't set a cutoff time
        
        # Get hot posts with appropriate limit based on timeframe
        post_limit = 50  # Default limit
        if timeframe in ["week", "month", "year", "all"]:
            post_limit = 200  # Increase limit for longer timeframes
        
        hot_posts = subreddit.hot(limit=post_limit)
        
        tickers_reddit = []
        stock_sentiments = defaultdict(list)
        processed_posts = []  # Track processed posts
        
        for post in hot_posts:
            # Skip posts older than cutoff time (except for "all" timeframe)
            if timeframe != "all" and datetime.fromtimestamp(post.created_utc) < cutoff_time:
                continue
                
            # Store post info
            processed_posts.append({
                'title': post.title,
                'created_utc': post.created_utc,
                'score': post.score,
                'num_comments': post.num_comments
            })
            
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
                # Skip comments older than cutoff time (except for "all" timeframe)
                if timeframe != "all" and datetime.fromtimestamp(comment.created_utc) < cutoff_time:
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
        top_stocks = Counter(tickers_reddit).most_common(20)
        
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
            "timeframe": timeframe,
            "top_stocks": top_stocks,
            "sentiment_results": sentiment_results,
            "processed_posts": processed_posts  # Include processed posts in the output
        }
    
    def _analyze_text(self, text):
        """Analyze text for stock mentions"""
        mentions = self._extract_stock_mentions(text)
        return mentions