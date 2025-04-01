def web_search(search_term, explanation=""):
    """
    Wrapper for the web search tool.
    Returns formatted search results.
    """
    try:
        # Use the web_search tool
        from app.tools import web_search as tool_web_search
        
        # Get search results
        results = tool_web_search(
            search_term=search_term,
            explanation=explanation
        )
        
        # Format the results
        formatted_results = []
        for result in results:
            formatted_result = {
                'title': result.get('title', ''),
                'content': result.get('content', result.get('snippet', '')),
                'url': result.get('url', '#'),
                'date': result.get('date', 'Today')
            }
            formatted_results.append(formatted_result)
        
        return formatted_results
        
    except Exception as e:
        print(f"Error in web search tool wrapper: {str(e)}")
        return [] 