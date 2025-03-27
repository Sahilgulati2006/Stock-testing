import praw
import re
from collections import defaultdict, Counter
from transformers import pipeline, AutoTokenizer
from datetime import date
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
        
        # Load NASDAQ tickers
        self.tickers_nasdaq = self._load_nasdaq_tickers()
    
    def _load_nasdaq_tickers(self):
        """Load NASDAQ tickers from CSV"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        nasdaq_path = os.path.join(current_dir, 'nasdaq-listed.csv')
        df = pd.read_csv(nasdaq_path)
        return [str(ticker).strip() for ticker in df['Symbol'].dropna().tolist()]
    
    def _split_text_into_chunks(self, text, max_length=510):
        """Split text for sentiment analysis"""
        tokenized_text = tokenizer.encode(text, truncation=True, max_length=max_length)
        return [tokenizer.decode(tokenized_text[i:i+max_length]) 
                for i in range(0, len(tokenized_text), max_length)]
    
    def analyze_subreddit(self, subreddit_name="wallstreetbets"):
        """Analyze stock mentions and sentiment in a subreddit"""
        subreddit = self.reddit.subreddit(subreddit_name)
        hot_posts = subreddit.hot(limit=Config.MAX_REDDIT_POSTS)
        
        tickers_reddit = []
        stock_sentiments = defaultdict(list)
        
        for post in hot_posts:
            # Process post title and body
            full_text = f"{post.title.strip()} {post.selftext.strip() if post.selftext else ''}"
            
            if full_text:
                chunks = self._split_text_into_chunks(full_text)
                sentiments = [sentiment_analyzer(chunk)[0]['label'] for chunk in chunks]
                
                for ticker in self.tickers_nasdaq:
                    if ticker in full_text:
                        tickers_reddit.append(ticker)
                        stock_sentiments[ticker].extend(sentiments)
            
            # Process comments
            post.comments.replace_more(limit=0)
            for comment in post.comments.list():
                comment_text = comment.body.strip()
                if comment_text:
                    chunks = self._split_text_into_chunks(comment_text)
                    sentiments = [sentiment_analyzer(chunk)[0]['label'] for chunk in chunks]
                    
                    for ticker in self.tickers_nasdaq:
                        if ticker in comment_text:
                            tickers_reddit.append(ticker)
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
        
        return {
            "date": date.today(),
            "subreddit": subreddit_name,
            "top_stocks": top_stocks,
            "sentiment_results": sentiment_results
        }