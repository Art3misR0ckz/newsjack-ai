import requests
from bs4 import BeautifulSoup


def scrape_brand_website(url):

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                )
            }
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Title
        title = (
            soup.title.get_text(strip=True)
            if soup.title
            else ""
        )

        # Meta description
        meta_desc = ""

        meta = soup.find(
            "meta",
            attrs={"name": "description"}
        )

        if meta:
            meta_desc = meta.get("content", "")

        # Headings
        headings = []

        for tag in soup.find_all(
            ["h1", "h2", "h3"]
        )[:20]:

            text = tag.get_text(
                strip=True
            )

            if text:
                headings.append(text)

        # Paragraphs
        paragraphs = []

        for tag in soup.find_all("p")[:30]:

            text = tag.get_text(
                strip=True
            )

            if len(text) > 30:
                paragraphs.append(text)

        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "paragraphs": paragraphs
        }

    except Exception as e:

        print(f"ERROR: {e}")

        return None