"""
Duck News Module
Henter nyheter fra NRK via RSS feeds.
Gratis, ingen API-nøkkel nødvendig.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional


# NRK RSS feeds - kategorier
NRK_FEEDS = {
    'toppsaker': 'https://www.nrk.no/toppsaker.rss',
    'siste': 'https://www.nrk.no/nyheter/siste.rss',
    'sport': 'https://www.nrk.no/sport/toppsaker.rss',
    'kultur': 'https://www.nrk.no/kultur/toppsaker.rss',
    'norge': 'https://www.nrk.no/norge/toppsaker.rss',
    'urix': 'https://www.nrk.no/urix/toppsaker.rss',
    'sapmi': 'https://www.nrk.no/sapmi/toppsaker.rss',
    'klima': 'https://www.nrk.no/klima/toppsaker.rss',
    'teknologi': 'https://www.nrk.no/teknologi/toppsaker.rss',
    'livsstil': 'https://www.nrk.no/livsstil/toppsaker.rss',
    'ytring': 'https://www.nrk.no/ytring/toppsaker.rss',
}

# Alias-mapping for naturlig språk
CATEGORY_ALIASES = {
    'nyheter': 'toppsaker',
    'topp': 'toppsaker',
    'hovedsaker': 'toppsaker',
    'siste nytt': 'siste',
    'nyeste': 'siste',
    'utenriks': 'urix',
    'verden': 'urix',
    'internasjonalt': 'urix',
    'innenriks': 'norge',
    'tech': 'teknologi',
    'it': 'teknologi',
    'data': 'teknologi',
    'kunst': 'kultur',
    'musikk': 'kultur',
    'film': 'kultur',
    'miljø': 'klima',
    'natur': 'klima',
    'helse': 'livsstil',
    'mat': 'livsstil',
    'meninger': 'ytring',
    'debatt': 'ytring',
    'kronikk': 'ytring',
    'samisk': 'sapmi',
    'ol': 'sport',
    'fotball': 'sport',
}


def _resolve_category(category: str) -> str:
    """Løs opp kategori fra alias eller naturlig språk"""
    cat = category.lower().strip()
    if cat in NRK_FEEDS:
        return cat
    if cat in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cat]
    return 'toppsaker'  # Default


def _parse_pub_date(pub_date_str: str) -> Optional[str]:
    """Parse RSS pubDate til lesbar norsk tid"""
    try:
        # Format: "Sat, 07 Feb 2026 12:54:26 GMT"
        dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
        # Norske dagnavn
        dag_navn = {0: 'man', 1: 'tir', 2: 'ons', 3: 'tor', 4: 'fre', 5: 'lør', 6: 'søn'}
        dag = dag_navn.get(dt.weekday(), '')
        return f"{dag} {dt.strftime('%H:%M')}"
    except Exception:
        return pub_date_str


def get_nrk_news(category: str = 'toppsaker', count: int = 5) -> str:
    """
    Hent nyheter fra NRK RSS feed.

    Args:
        category: Nyhetskategori (toppsaker, sport, kultur, norge, urix, etc.)
        count: Antall nyheter å hente (default 5, max 15)

    Returns:
        Formatert streng med nyheter
    """
    resolved = _resolve_category(category)
    url = NRK_FEEDS.get(resolved, NRK_FEEDS['toppsaker'])

    try:
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1 (Samantha; +https://github.com/osmund/chatgpt-and)'
        }

        print(f"📰 Henter NRK nyheter: {resolved} ({url})", flush=True)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        channel = root.find('channel')

        if channel is None:
            return "❌ Kunne ikke parse NRK RSS-feed"

        items = channel.findall('item')
        count = min(count, 15)
        items = items[:count]

        if not items:
            return f"Fant ingen nyheter i kategorien {resolved}"

        # Bygg resultat
        category_label = resolved.capitalize()
        results = [f"📰 NRK {category_label} ({len(items)} saker):\n"]

        for i, item in enumerate(items, 1):
            title_el = item.find('title')
            desc_el = item.find('description')
            pub_date_el = item.find('pubDate')
            categories = [c.text for c in item.findall('category') if c.text]

            title = title_el.text if title_el is not None else 'Ingen tittel'
            desc = desc_el.text if desc_el is not None else ''
            pub_date = _parse_pub_date(pub_date_el.text) if pub_date_el is not None else ''

            results.append(f"{i}. {title}")

            if desc:
                # Trunkér lange beskrivelser
                desc_clean = desc.strip()
                if len(desc_clean) > 300:
                    desc_clean = desc_clean[:300] + "..."
                results.append(f"   {desc_clean}")

            meta_parts = []
            if pub_date:
                meta_parts.append(pub_date)
            if categories:
                meta_parts.append(', '.join(categories[:3]))
            if meta_parts:
                results.append(f"   [{' | '.join(meta_parts)}]")

            results.append("")  # Blank linje mellom saker

        # Legg til tilgjengelige kategorier som hint
        results.append(f"Tilgjengelige kategorier: {', '.join(NRK_FEEDS.keys())}")

        formatted = "\n".join(results)
        print(f"✅ Hentet {len(items)} NRK-nyheter fra {resolved}", flush=True)
        return formatted

    except requests.Timeout:
        return "❌ NRK svarte ikke (timeout)"
    except requests.RequestException as e:
        return f"❌ Feil ved henting av NRK-nyheter: {str(e)}"
    except ET.ParseError as e:
        return f"❌ Kunne ikke parse NRK RSS: {str(e)}"
    except Exception as e:
        print(f"❌ Uventet feil i get_nrk_news: {e}", flush=True)
        return f"❌ Kunne ikke hente nyheter: {str(e)}"


# === Andre norske nyhetskilder (VG, Aftenposten) ===

NEWS_SOURCES = {
    'vg': {
        'name': 'VG',
        'url': 'https://www.vg.no/rss/feed/',
        'emoji': '📰',
    },
    'aftenposten': {
        'name': 'Aftenposten',
        'url': 'https://www.aftenposten.no/rss',
        'emoji': '📰',
    },
    'aftenbladet': {
        'name': 'Stavanger Aftenblad',
        'url': 'https://www.aftenbladet.no/rss',
        'emoji': '📰',
    },
}

# Alias for naturlig språk
SOURCE_ALIASES = {
    'verdens gang': 'vg',
    'aften': 'aftenposten',
    'apost': 'aftenposten',
    'ap': 'aftenposten',
    'stavanger aftenblad': 'aftenbladet',
    'stavanger aftenbladet': 'aftenbladet',
    'sa': 'aftenbladet',
}


def get_news_headlines(source: str = 'vg', count: int = 5) -> str:
    """
    Hent nyhetsoverskrifter fra norske aviser (VG, Aftenposten).

    Args:
        source: Kilde - 'vg' eller 'aftenposten'
        count: Antall overskrifter (default 5, max 15)

    Returns:
        Formatert streng med nyhetsoverskrifter
    """
    # Oppløs alias
    src = source.lower().strip()
    if src in SOURCE_ALIASES:
        src = SOURCE_ALIASES[src]
    if src not in NEWS_SOURCES:
        available = ', '.join(NEWS_SOURCES.keys())
        return f"Ukjent kilde '{source}'. Tilgjengelige kilder: {available}. Bruk get_nrk_news for NRK-nyheter."

    source_info = NEWS_SOURCES[src]
    url = source_info['url']
    name = source_info['name']
    emoji = source_info['emoji']

    try:
        headers = {
            'User-Agent': 'ChatGPTDuck/2.1 (Samantha; +https://github.com/osmund/chatgpt-and)'
        }

        print(f"{emoji} Henter nyheter fra {name}: {url}", flush=True)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        channel = root.find('channel')

        if channel is None:
            return f"❌ Kunne ikke parse {name} RSS-feed"

        items = channel.findall('item')
        count = min(count, 15)
        items = items[:count]

        if not items:
            return f"Fant ingen nyheter fra {name}"

        results = [f"{emoji} {name} - Siste nytt ({len(items)} saker):\n"]

        for i, item in enumerate(items, 1):
            title_el = item.find('title')
            desc_el = item.find('description')
            pub_date_el = item.find('pubDate')
            category_el = item.find('category')

            title = title_el.text.strip() if title_el is not None and title_el.text else 'Ingen tittel'
            desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ''
            pub_date = _parse_pub_date(pub_date_el.text) if pub_date_el is not None and pub_date_el.text else ''
            category = category_el.text.strip() if category_el is not None and category_el.text else ''

            results.append(f"{i}. {title}")

            if desc:
                desc_clean = desc.strip()
                if len(desc_clean) > 300:
                    desc_clean = desc_clean[:300] + "..."
                results.append(f"   {desc_clean}")

            meta_parts = []
            if pub_date:
                meta_parts.append(pub_date)
            if category:
                meta_parts.append(category)
            if meta_parts:
                results.append(f"   [{' | '.join(meta_parts)}]")

            results.append("")

        results.append(f"Tilgjengelige kilder: {', '.join(NEWS_SOURCES.keys())}. Bruk get_nrk_news for NRK.")

        formatted = "\n".join(results)
        print(f"✅ Hentet {len(items)} saker fra {name}", flush=True)
        return formatted

    except requests.Timeout:
        return f"❌ {name} svarte ikke (timeout)"
    except requests.RequestException as e:
        return f"❌ Feil ved henting av {name}-nyheter: {str(e)}"
    except ET.ParseError as e:
        return f"❌ Kunne ikke parse {name} RSS: {str(e)}"
    except Exception as e:
        print(f"❌ Uventet feil i get_news_headlines ({name}): {e}", flush=True)
        return f"❌ Kunne ikke hente nyheter fra {name}: {str(e)}"
