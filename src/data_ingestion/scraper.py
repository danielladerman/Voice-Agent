import requests
from bs4 import BeautifulSoup

def scrape_website(url: str) -> str:
    """
    Scrapes a website and returns the text content.

    Args:
        url: The URL of the website to scrape.

    Returns:
        The text content of the website, or an empty string if an error occurs.
    """
    try:
        response = requests.get(url)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- A More Intelligent Content Extraction ---
        # Instead of removing noisy tags, we'll try to find the main content directly.
        # This is more robust as modern websites use semantic HTML tags.
        
        main_content = soup.find('main')
        if not main_content:
            main_content = soup.find('article')
        if not main_content:
            main_content = soup.find('body') # Fallback to the whole body if no main/article

        # Once we have the main content block, we remove any lingering noisy tags from it.
        for script_or_style in main_content(['script', 'style', 'nav', 'footer', 'header']):
            script_or_style.decompose()

        # Get text from the cleaned main content block
        text = main_content.get_text(separator=' ', strip=True)
        
        # --- Clean up whitespace ---
        # Replace multiple spaces/newlines with a single space for cleaner text.
        text = ' '.join(text.split())

        return text

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return ""

if __name__ == '__main__':
    # This block allows us to test the scraper directly
    # Example usage:
    test_url = "https://python.langchain.com/v0.2/docs/introduction/"
    print(f"Scraping {test_url}...")
    
    content = scrape_website(test_url)
    
    if content:
        print("Successfully scraped content. First 500 characters:")
        print(content[:500] + "...")
    else:
        print("Failed to scrape content.") 