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

        # Remove script and style elements
        for script_or_style in soup(['script', 'style', 'nav', 'footer', 'header']):
            script_or_style.decompose()

        # Find all meaningful text blocks and join them
        tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'span', 'div']
        text_blocks = [tag.get_text(strip=True) for tag in soup.find_all(tags)]
        text = ' '.join(text_blocks)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)

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