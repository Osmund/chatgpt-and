"""
Duck Wikipedia Module
Slår opp artikler fra norsk Wikipedia (bokmål).
Gratis, ingen API-nøkkel nødvendig.
"""

import requests
from typing import Optional


WIKI_API_URL = 'https://no.wikipedia.org/w/api.php'
WIKI_REST_URL = 'https://no.wikipedia.org/api/rest_v1'

HEADERS = {
    'User-Agent': 'ChatGPTDuck/2.1 (Samantha; +https://github.com/osmund/chatgpt-and)',
    'Accept': 'application/json',
}


def wikipedia_lookup(query: str, sentences: int = 5) -> str:
    """
    Slå opp et tema på norsk Wikipedia.

    Args:
        query: Søketerm eller emne (f.eks. 'Nidarosdomen', 'fotosyntese', 'Roald Amundsen')
        sentences: Antall setninger å returnere (default 5)

    Returns:
        Formatert streng med Wikipedia-artikkelsammendrag
    """
    try:
        print(f"📚 Wikipedia-oppslag: '{query}'", flush=True)

        # Først: prøv direkte oppslag via REST API (raskest)
        summary = _get_page_summary(query)

        if not summary:
            # Fallback: søk etter artikkel
            title = _search_article(query)
            if title:
                summary = _get_page_summary(title)

        if not summary:
            return f"Fant ingen Wikipedia-artikkel om '{query}'. Prøv et annet søkeord."

        # Bygg resultat
        title = summary.get('title', query)
        extract = summary.get('extract', '')
        description = summary.get('description', '')

        # Begrens lengde
        if sentences and extract:
            # Del på setninger (punktum etterfulgt av mellomrom eller slutt)
            parts = extract.split('. ')
            if len(parts) > sentences:
                extract = '. '.join(parts[:sentences]) + '.'

        results = [f"📚 Wikipedia: {title}"]
        if description:
            results.append(f"({description})")
        results.append("")
        results.append(extract)

        # Legg til URL
        page_url = summary.get('content_urls', {}).get('desktop', {}).get('page', '')
        if page_url:
            results.append(f"\n🔗 {page_url}")

        formatted = "\n".join(results)
        print(f"✅ Wikipedia-artikkel funnet: {title}", flush=True)
        return formatted

    except Exception as e:
        print(f"❌ Wikipedia-feil: {e}", flush=True)
        return f"❌ Kunne ikke slå opp på Wikipedia: {str(e)}"


def _get_page_summary(title: str) -> Optional[dict]:
    """Hent artikkelsammendrag via REST API"""
    try:
        # URL-encode title med underscore i stedet for mellomrom
        encoded_title = title.strip().replace(' ', '_')
        url = f"{WIKI_REST_URL}/page/summary/{encoded_title}"

        response = requests.get(url, headers=HEADERS, timeout=10)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        # Sjekk at vi fikk en ekte artikkel (ikke disambiguation etc.)
        if data.get('type') == 'disambiguation':
            # Prøv å hente første alternativ
            return None

        if data.get('extract'):
            return data

        return None

    except Exception:
        return None


def _search_article(query: str) -> Optional[str]:
    """Søk etter artikkel og returner beste treff"""
    try:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'srlimit': 3,
            'srprop': 'snippet',
            'format': 'json',
        }

        response = requests.get(WIKI_API_URL, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()
        results = data.get('query', {}).get('search', [])

        if results:
            return results[0].get('title')

        return None

    except Exception:
        return None


def wikipedia_random() -> str:
    """
    Hent en tilfeldig Wikipedia-artikkel.
    Morsomt for 'visste du at...'-øyeblikk.

    Returns:
        Formatert streng med tilfeldig artikkel
    """
    try:
        print(f"🎲 Henter tilfeldig Wikipedia-artikkel...", flush=True)

        # Bruk MediaWiki API for å finne en tilfeldig artikkel
        params = {
            'action': 'query',
            'list': 'random',
            'rnnamespace': 0,  # Bare hovedartikler
            'rnlimit': 1,
            'format': 'json',
        }

        response = requests.get(WIKI_API_URL, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()
        random_articles = data.get('query', {}).get('random', [])

        if not random_articles:
            return "Kunne ikke finne en tilfeldig artikkel."

        title = random_articles[0].get('title', '')
        if not title:
            return "Kunne ikke finne en tilfeldig artikkel."

        # Hent sammendrag
        summary = _get_page_summary(title)
        if not summary or not summary.get('extract'):
            return f"Fant artikkelen '{title}' men den hadde ingen tekst."

        extract = summary.get('extract', '')
        description = summary.get('description', '')

        # Begrens lengde
        parts = extract.split('. ')
        if len(parts) > 4:
            extract = '. '.join(parts[:4]) + '.'

        results = [f"🎲 Visste du at...?\n"]
        results.append(f"📚 {title}")
        if description:
            results.append(f"({description})")
        results.append("")
        results.append(extract)

        formatted = "\n".join(results)
        print(f"✅ Tilfeldig artikkel: {title}", flush=True)
        return formatted

    except Exception as e:
        print(f"❌ Wikipedia random feil: {e}", flush=True)
        return f"❌ Kunne ikke hente tilfeldig artikkel: {str(e)}"
