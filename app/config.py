import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', 'hxGeYKs1qclcdpNgPzniVjNvtgIcbulg')
    REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '_f9G2wmqD_D-8BU7usAkuw')
    REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', 'gLt3IkPt4B-GrPV-yQ44-LUy2XXmnQ')
    
    # Paths
    NASDAQ_LIST_PATH = os.path.join(os.path.dirname(__file__), 'app/nasdaq-listed.csv')

    # Other settings
    SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"
    MAX_REDDIT_POSTS = 50
    MAX_NEWS_ARTICLES = 10