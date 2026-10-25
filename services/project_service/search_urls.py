"""Search-engine result URLs that agents open for a keyword query."""

from urllib.parse import quote, urlencode


def search_click_url(text: str, engine: str = "google") -> str:
    """URL of the search results page for ``text`` on ``engine`` (google / yandex / bing; default google)."""
    engines = {
        "google": f"https://www.google.com/search?{urlencode({'q': text})}",
        "yandex": f"https://yandex.ru/search/?text={quote(text)}",
        "bing": f"https://www.bing.com/search?{urlencode({'q': text})}",
    }
    return engines.get(engine, engines["google"])
