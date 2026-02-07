"""
Duck Web Search Module
Handles web search via Brave Search API and fetches article content
"""

import os
import requests
import re
import trafilatura
from dotenv import load_dotenv

load_dotenv()

BRAVE_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')
BRAVE_SEARCH_URL = 'https://api.search.brave.com/res/v1/web/search'

# Domener som er trege, blokkerer bots, eller krever JavaScript for innhold
SLOW_DOMAINS = {
    'olympics.com',
    'theathletic.com',
    'nytimes.com',
    'wsj.com',
    'bloomberg.com',
    'paywallsite.com',
}


def _is_slow_domain(url: str) -> bool:
    """Sjekk om en URL er fra et kjent tregt/blokkert domene"""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        return any(blocked in domain for blocked in SLOW_DOMAINS)
    except Exception:
        return False


def _fetch_article_content(url: str, max_length: int = 3000) -> str:
    """
    Henter hovedinnholdet fra en nettside via trafilatura.
    
    Args:
        url: URL til siden
        max_length: Maks antall tegn å returnere
        
    Returns:
        Hovedteksten fra siden, eller None hvis feil
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        
        # Ekstraher innhold med tabeller inkludert
        text = trafilatura.extract(
            downloaded,
            include_tables=True,
            include_links=False,
            include_images=False,
            include_comments=False,
            favor_recall=True,  # Hent mer innhold fremfor presisjon
        )
        
        if not text:
            return None
        
        # Rens og begrens
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:max_length] if text else None
        
    except Exception as e:
        print(f"⚠️ Kunne ikke hente innhold fra {url}: {e}", flush=True)
        return None


def web_search(query: str, count: int = 5) -> str:
    """
    Søker på nettet via Brave Search API
    
    Args:
        query: Søkeord/spørsmål
        count: Antall resultater (default 5)
        
    Returns:
        Formatert streng med søkeresultater
    """
    if not BRAVE_API_KEY:
        return "❌ Brave Search API-nøkkel mangler i .env fil"
    
    try:
        headers = {
            'X-Subscription-Token': BRAVE_API_KEY,
            'Accept': 'application/json'
        }
        
        params = {
            'q': query,
            'count': count,
            'text_decorations': False,
            'safesearch': 'moderate'
        }
        
        print(f"🔍 Søker på nettet: '{query}'", flush=True)
        response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Formater resultater
        results = []
        
        # Web resultater
        if 'web' in data and 'results' in data['web']:
            web_results = data['web']['results'][:count]
            if web_results:
                results.append("🌐 Søkeresultater:")
                for i, result in enumerate(web_results, 1):
                    title = result.get('title', 'Ingen tittel')
                    description = result.get('description', 'Ingen beskrivelse')
                    url = result.get('url', '')
                    age = result.get('age', '')
                    
                    results.append(f"\n{i}. {title}")
                    
                    # Prøv å hente faktisk innhold fra siden (kun første 2 resultater, hopp over trege domener)
                    if i <= 2 and not _is_slow_domain(url):
                        content = _fetch_article_content(url)
                        if content:
                            results.append(f"   Innhold: {content}")
                        else:
                            results.append(f"   Beskrivelse: {description}")
                    else:
                        if _is_slow_domain(url) and i <= 2:
                            results.append(f"   Beskrivelse: {description}")
                            results.append(f"   (Hopper over innholdshenting - tregt nettsted)")
                        else:
                            results.append(f"   Beskrivelse: {description}")
                    
                    if age:
                        results.append(f"   Publisert: {age}")
                    results.append(f"   Kilde: {url}")
        
        # News resultater
        if 'news' in data and 'results' in data['news']:
            news_results = data['news']['results'][:3]
            if news_results:
                results.append("\n\n📰 Siste nyheter:")
                for i, news in enumerate(news_results, 1):
                    title = news.get('title', 'Ingen tittel')
                    description = news.get('description', '')
                    url = news.get('url', '')
                    age = news.get('age', '')
                    
                    results.append(f"\n{i}. {title}")
                    if description:
                        results.append(f"   {description}")
                    if age:
                        results.append(f"   {age}")
                    results.append(f"   Kilde: {url}")
        
        # FAQ/Featured snippets
        if 'faq' in data and 'results' in data['faq']:
            faq_results = data['faq']['results'][:2]
            if faq_results:
                results.append("\n\n💡 Direkte svar:")
                for faq in faq_results:
                    question = faq.get('question', '')
                    answer = faq.get('answer', '')
                    if question and answer:
                        results.append(f"\nQ: {question}")
                        results.append(f"A: {answer}")
        
        if not results:
            return f"Fant ingen resultater for '{query}'"
        
        formatted = "\n".join(results)
        print(f"✅ Fant {len(web_results) if 'web_results' in locals() else 0} resultater", flush=True)
        return formatted
        
    except requests.Timeout:
        return "❌ Søket tok for lang tid (timeout)"
    except requests.RequestException as e:
        return f"❌ Feil ved søk: {str(e)}"
    except Exception as e:
        print(f"❌ Uventet feil i web_search: {e}", flush=True)
        return f"❌ Kunne ikke søke på nettet: {str(e)}"
