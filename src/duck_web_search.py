"""
Duck Web Search Module
Handles web search via Brave Search API and fetches article content
"""

import os
import requests
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BRAVE_API_KEY = os.getenv('BRAVE_SEARCH_API_KEY')
BRAVE_SEARCH_URL = 'https://api.search.brave.com/res/v1/web/search'


def _fetch_article_content(url: str, max_length: int = 3000) -> str:
    """
    Henter hovedinnholdet fra en nettside
    
    Args:
        url: URL til siden
        max_length: Maks antall tegn å returnere
        
    Returns:
        Hovedteksten fra siden, eller None hvis feil
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; DuckBot/1.0; +http://example.com/bot)'
        }
        
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Fjern uønskede elementer
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement', 'iframe']):
            tag.decompose()
        
        # Prøv å hente tabelldata (viktig for medaljeoversikter etc.)
        tables = soup.find_all('table')
        table_text = ""
        for table in tables[:2]:  # Maks 2 tabeller
            rows = table.find_all('tr')
            for row in rows[:20]:  # Maks 20 rader
                cells = row.find_all(['td', 'th'])
                if cells:
                    table_text += " | ".join(cell.get_text(strip=True) for cell in cells) + "\n"
        
        # Prøv å finne hovedinnholdet
        article = (
            soup.find('article') or 
            soup.find('main') or 
            soup.find('div', class_=re.compile(r'article|content|post|entry', re.I))
        )
        
        if article:
            text = article.get_text(separator=' ', strip=True)
        else:
            # Fallback: hent all tekst fra body
            body = soup.find('body')
            text = body.get_text(separator=' ', strip=True) if body else ''
        
        # Rens opp tekst
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Legg til tabelldata først (verdifullt for medaljer, statistikk etc.)
        if table_text:
            combined = f"TABELLDATA:\n{table_text.strip()}\n\nTEKST: {text}"
            return combined[:max_length] if combined else None
        
        # Returner maks lengde
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
                    
                    # Prøv å hente faktisk innhold fra siden (kun første 2 resultater)
                    if i <= 2:
                        content = _fetch_article_content(url)
                        if content:
                            results.append(f"   Innhold: {content}")
                        else:
                            results.append(f"   Beskrivelse: {description}")
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
