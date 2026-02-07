"""
Duck Wikipedia Module
Slår opp artikler fra Wikipedia (norsk og engelsk).
Gratis, ingen API-nøkkel nødvendig.
"""

import requests
from typing import Optional


HEADERS = {
    'User-Agent': 'ChatGPTDuck/2.1 (Samantha; +https://github.com/osmund/chatgpt-and)',
    'Accept': 'application/json',
}

# Støttede språk
WIKI_LANGUAGES = {
    'no': {'name': 'norsk', 'emoji': '🇳🇴'},
    'en': {'name': 'English', 'emoji': '🇬🇧'},
}


def _wiki_api_url(language: str = 'no') -> str:
    """Returnerer MediaWiki API URL for valgt språk"""
    return f'https://{language}.wikipedia.org/w/api.php'


def _wiki_rest_url(language: str = 'no') -> str:
    """Returnerer REST API URL for valgt språk"""
    return f'https://{language}.wikipedia.org/api/rest_v1'


def wikipedia_lookup(query: str, sentences: int = 5, language: str = 'no') -> str:
    """
    Slå opp et tema på Wikipedia.

    Args:
        query: Søketerm eller emne (f.eks. 'Nidarosdomen', 'fotosyntese', 'Roald Amundsen')
        sentences: Antall setninger å returnere (default 5)
        language: Språkkode ('no' for norsk, 'en' for engelsk). Default 'no'.

    Returns:
        Formatert streng med Wikipedia-artikkelsammendrag
    """
    # Valider språk
    if language not in WIKI_LANGUAGES:
        language = 'no'

    lang_info = WIKI_LANGUAGES[language]

    try:
        print(f"📚 Wikipedia-oppslag ({lang_info['name']}): '{query}'", flush=True)

        # Først: prøv direkte oppslag via REST API (raskest)
        summary = _get_page_summary(query, language)

        if not summary:
            # Fallback: søk etter artikkel
            title = _search_article(query, language)
            if title:
                summary = _get_page_summary(title, language)

        if not summary:
            return f"Fant ingen Wikipedia-artikkel om '{query}' ({lang_info['name']}). Prøv et annet søkeord eller språk."

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

        results = [f"📚 Wikipedia {lang_info['emoji']}: {title}"]
        if description:
            results.append(f"({description})")
        results.append("")
        results.append(extract)

        # Legg til URL
        page_url = summary.get('content_urls', {}).get('desktop', {}).get('page', '')
        if page_url:
            results.append(f"\n🔗 {page_url}")

        formatted = "\n".join(results)
        print(f"✅ Wikipedia-artikkel funnet ({lang_info['name']}): {title}", flush=True)
        return formatted

    except Exception as e:
        print(f"❌ Wikipedia-feil: {e}", flush=True)
        return f"❌ Kunne ikke slå opp på Wikipedia: {str(e)}"


def _get_page_summary(title: str, language: str = 'no') -> Optional[dict]:
    """Hent artikkelsammendrag via REST API"""
    try:
        # URL-encode title med underscore i stedet for mellomrom
        encoded_title = title.strip().replace(' ', '_')
        url = f"{_wiki_rest_url(language)}/page/summary/{encoded_title}"

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


def _search_article(query: str, language: str = 'no') -> Optional[str]:
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

        response = requests.get(_wiki_api_url(language), params=params, headers=HEADERS, timeout=10)
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

        response = requests.get(_wiki_api_url('no'), params=params, headers=HEADERS, timeout=10)
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
