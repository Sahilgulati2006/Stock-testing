def web_search(search_term, explanation=""):
    """
    Search the web for the given search term.
    Returns a list of search results.
    """
    try:
        # Import the web_search tool from the available tools
        from app.web_search_tool import web_search as external_web_search
        
        # Format the search term to focus on recent news
        search_term = f"{search_term} latest news today"
        
        # Get search results
        raw_results = external_web_search(
            search_term=search_term,
            explanation=explanation or f"Searching for {search_term}"
        )
        
        # Process and format the results
        formatted_results = []
        for result in raw_results[:3]:  # Limit to top 3 results
            # Extract title and content
            title = result.get('title', '').split(' - ')[0]  # Remove site name if present
            content = result.get('content', '')
            
            # Format the result
            formatted_result = {
                'title': title[:100],  # Limit title length
                'snippet': content[:200] + '...' if len(content) > 200 else content,  # Limit snippet length
                'url': result.get('url', '#'),
                'date': 'Today'  # Since we're searching for today's news
            }
            formatted_results.append(formatted_result)
        
        return formatted_results if formatted_results else [{
            'title': f'Latest Market Data for {search_term}',
            'snippet': 'Visit Yahoo Finance for detailed market analysis and real-time stock quotes.',
            'url': f'https://finance.yahoo.com/quote/{search_term.split()[0]}',
            'date': 'Today'
        }]
        
    except Exception as e:
        print(f"Error in web search tool: {str(e)}")
        return [{
            'title': f'Market Updates for {search_term.split()[0]}',
            'snippet': 'Visit Yahoo Finance for the latest market data and financial news.',
            'url': f'https://finance.yahoo.com/quote/{search_term.split()[0]}',
            'date': 'Today'
        }] 