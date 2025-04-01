from datetime import datetime, timedelta
from app.tools import web_search as web_search_tool

def web_search(query):
    """
    Search the web for news articles and format the results.
    Returns a list of dictionaries containing article information.
    """
    try:
        # Use the web_search tool to get results
        raw_results = web_search_tool(search_term=query, explanation="Searching for news articles")
        results = []
        
        # Process each result into a standardized format
        for result in raw_results:
            # Try to parse the date if available
            try:
                date = result.get('date', datetime.now().strftime('%Y-%m-%d'))
            except:
                date = 'Recent'
                
            # Format the result
            formatted_result = {
                'title': result.get('title', ''),
                'snippet': result.get('snippet', ''),
                'url': result.get('url', ''),
                'date': date
            }
            results.append(formatted_result)
            
        return results
        
    except Exception as e:
        print(f"Error in web search: {str(e)}")
        return [] 