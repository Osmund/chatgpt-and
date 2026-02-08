"""
OL-medaljeoversikt fra Wikipedia.
Parser strukturerte medaljedata fra Wikipedia sin medaljetabell.
Oppdateres i nær-sanntid av Wikipedia-redaktører under pågående OL.
"""

import re
import requests
import logging

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "oDuckberry/1.0 (anda@oduckberry.local)"}
WIKI_API = "https://en.wikipedia.org/w/api.php"

# IOC-koder til norske/vanlige landnavn
IOC_TO_NAME = {
    "NOR": "Norge",
    "SWE": "Sverige",
    "GER": "Tyskland",
    "AUT": "Østerrike",
    "SUI": "Sveits",
    "FRA": "Frankrike",
    "ITA": "Italia",
    "CAN": "Canada",
    "USA": "USA",
    "FIN": "Finland",
    "JPN": "Japan",
    "CHN": "Kina",
    "KOR": "Sør-Korea",
    "NED": "Nederland",
    "CZE": "Tsjekkia",
    "SLO": "Slovenia",
    "SVK": "Slovakia",
    "POL": "Polen",
    "AUS": "Australia",
    "GBR": "Storbritannia",
    "NZL": "New Zealand",
    "ESP": "Spania",
    "BEL": "Belgia",
    "UKR": "Ukraina",
    "ROC": "Russland (ROC)",
    "AIN": "Nøytrale utøvere",
    "ROU": "Romania",
    "BLR": "Hviterussland",
    "EST": "Estland",
    "LAT": "Latvia",
    "LTU": "Litauen",
    "BUL": "Bulgaria",
    "CRO": "Kroatia",
    "DEN": "Danmark",
    "KAZ": "Kasakhstan",
    "UZB": "Usbekistan",
    "GEO": "Georgia",
    "BIH": "Bosnia-Hercegovina",
    "MGL": "Mongolia",
}

# Engelsk → IOC-kode for vanlige land (for å støtte engelske søk)
ENGLISH_TO_IOC = {
    "norway": "NOR", "sweden": "SWE", "germany": "GER", "austria": "AUT",
    "switzerland": "SUI", "france": "FRA", "italy": "ITA", "canada": "CAN",
    "finland": "FIN", "japan": "JPN", "china": "CHN", "south korea": "KOR",
    "netherlands": "NED", "czech republic": "CZE", "czechia": "CZE",
    "slovenia": "SLO", "slovakia": "SVK", "poland": "POL", "australia": "AUS",
    "great britain": "GBR", "united kingdom": "GBR", "uk": "GBR",
    "new zealand": "NZL", "spain": "ESP", "belgium": "BEL", "ukraine": "UKR",
    "russia": "ROC", "romania": "ROU", "belarus": "BLR", "estonia": "EST",
    "latvia": "LAT", "lithuania": "LTU", "bulgaria": "BUL", "croatia": "CRO",
    "denmark": "DEN", "kazakhstan": "KAZ", "uzbekistan": "UZB", "georgia": "GEO",
}


def _get_country_name(ioc_code: str) -> str:
    """Konverter IOC-kode til norsk landnavn."""
    return IOC_TO_NAME.get(ioc_code, ioc_code)


def get_olympics_medals(top_n: int = 15, country: str = None) -> str:
    """Hent OL-medaljeoversikt fra Wikipedia.
    
    Args:
        top_n: Antall land å vise (default 15)
        country: Spesifikt land å fremheve (valgfri)
    
    Returns:
        Formatert medaljetabell for AI-kontekst
    """
    try:
        # Finn riktig Wikipedia-side for pågående/siste OL
        page_title = _find_olympics_medal_page()
        if not page_title:
            return "Kunne ikke finne OL-medaljetabell på Wikipedia."
        
        # Hent wikitext for medal table-seksjonen
        wikitext = _get_medal_table_wikitext(page_title)
        if not wikitext:
            return "Kunne ikke hente medaljedata fra Wikipedia."
        
        # Parse medaljedata
        medals = _parse_medal_data(wikitext)
        if not medals:
            return "Ingen medaljedata funnet ennå. OL har kanskje ikke startet?"
        
        # Sorter: gull først, så sølv, så bronse, så totalt
        medals.sort(key=lambda m: (-m["gold"], -m["silver"], -m["bronze"]))
        
        # Finn OL-navn fra sidetittel
        olympics_name = _extract_olympics_name(page_title)
        
        lines = [f"Medaljeoversikt - {olympics_name}:", ""]
        lines.append(f"{'#':>2}  {'Land':<22} {'🥇':>3} {'🥈':>3} {'🥉':>3} {'Tot':>4}")
        lines.append("-" * 45)
        
        # Finn spesifikt land (for highlight)
        country_lower = country.lower() if country else None
        country_found = False
        
        for i, entry in enumerate(medals[:top_n], 1):
            name = entry["name"]
            g, s, b = entry["gold"], entry["silver"], entry["bronze"]
            total = g + s + b
            
            if total == 0:
                continue
            
            marker = ""
            if country_lower and country_lower in name.lower():
                marker = " ⬅️"
                country_found = True
            
            lines.append(f"{i:>2}. {name:<22} {g:>3} {s:>3} {b:>3} {total:>4}{marker}")
        
        # Hvis spesifikt land ble spurt om men ikke i top_n, finn det
        if country_lower and not country_found:
            for i, entry in enumerate(medals, 1):
                name = entry["name"]
                if country_lower in name.lower():
                    g, s, b = entry["gold"], entry["silver"], entry["bronze"]
                    total = g + s + b
                    lines.append(f"  ...")
                    lines.append(f"{i:>2}. {name:<22} {g:>3} {s:>3} {b:>3} {total:>4} ⬅️")
                    break
        
        # Legg til total medaljer delt ut
        total_g = sum(m["gold"] for m in medals)
        total_s = sum(m["silver"] for m in medals)
        total_b = sum(m["bronze"] for m in medals)
        total_all = total_g + total_s + total_b
        lines.append("-" * 45)
        lines.append(f"    {'Totalt':<22} {total_g:>3} {total_s:>3} {total_b:>3} {total_all:>4}")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Feil ved henting av OL-medaljer: {e}")
        return f"Kunne ikke hente OL-medaljeoversikt: {e}"


def _find_olympics_medal_page() -> str:
    """Finn riktig Wikipedia-side for pågående/nylige OL."""
    from datetime import datetime
    
    year = datetime.now().year
    
    # Prøv pågående år først, deretter forrige
    candidates = [
        f"{year} Winter Olympics medal table",
        f"{year} Summer Olympics medal table",
        f"{year - 1} Winter Olympics medal table",
        f"{year - 1} Summer Olympics medal table",
    ]
    
    for title in candidates:
        try:
            resp = requests.get(WIKI_API, params={
                "action": "query",
                "titles": title,
                "format": "json",
            }, headers=HEADERS, timeout=5)
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            # Sjekk at siden finnes (ikke -1)
            for page_id, page in pages.items():
                if page_id != "-1":
                    return title
        except Exception:
            continue
    
    return None


def _get_medal_table_wikitext(page_title: str) -> str:
    """Hent wikitext for medal table-seksjonen."""
    try:
        # Finn seksjonsnummer for "Medal table"
        resp = requests.get(WIKI_API, params={
            "action": "parse",
            "page": page_title,
            "prop": "sections",
            "format": "json",
        }, headers=HEADERS, timeout=10)
        data = resp.json()
        
        section_idx = None
        for s in data.get("parse", {}).get("sections", []):
            if s["line"].lower() in ("medal table", "medal count"):
                section_idx = s["index"]
                break
        
        if section_idx is None:
            # Prøv hele siden
            section_idx = 0
        
        # Hent wikitext for den seksjonen
        resp = requests.get(WIKI_API, params={
            "action": "parse",
            "page": page_title,
            "prop": "wikitext",
            "section": section_idx,
            "format": "json",
        }, headers=HEADERS, timeout=10)
        data = resp.json()
        return data.get("parse", {}).get("wikitext", {}).get("*", "")
        
    except Exception as e:
        logger.error(f"Feil ved henting av Wikipedia-wikitext: {e}")
        return None


def _parse_medal_data(wikitext: str) -> list:
    """Parse medaljedata fra Wikipedia wikitext.
    
    Forventer format som:
    | gold_NOR = 5 | silver_NOR = 3 | bronze_NOR = 2
    """
    medals = {}
    
    # Finn alle gold/silver/bronze verdier
    pattern = r'\|\s*(gold|silver|bronze)_(\w+)\s*=\s*(\d+)'
    matches = re.findall(pattern, wikitext)
    
    for medal_type, country_code, count in matches:
        if country_code not in medals:
            medals[country_code] = {
                "code": country_code,
                "name": _get_country_name(country_code),
                "gold": 0,
                "silver": 0,
                "bronze": 0,
            }
        medals[country_code][medal_type] = int(count)
    
    return list(medals.values())


def _extract_olympics_name(page_title: str) -> str:
    """Konverter sidetittel til norsk OL-navn."""
    # "2026 Winter Olympics medal table" -> "Vinter-OL 2026"
    match = re.match(r"(\d{4})\s+(Winter|Summer)\s+Olympics", page_title)
    if match:
        year = match.group(1)
        season = "Vinter-OL" if match.group(2) == "Winter" else "Sommer-OL"
        return f"{season} {year}"
    return page_title.replace(" medal table", "")


def get_olympics_medal_details(country: str = "Norge") -> str:
    """Hent detaljerte medaljevinnere for et spesifikt land.
    
    Parser 'List of YYYY Winter/Summer Olympics medal winners' fra Wikipedia
    for å finne hvilke øvelser et land har tatt medaljer i.
    
    Args:
        country: Landnavn (norsk eller IOC-kode)
    
    Returns:
        Formatert liste med medaljevinnere per øvelse
    """
    try:
        page_title = _find_olympics_medal_page()
        if not page_title:
            return "Kunne ikke finne OL-medaljetabell."
        
        # Finn winners-siden
        winners_page = page_title.replace("medal table", "medal winners")
        winners_page = "List of " + winners_page
        
        # Finn IOC-kode(r) for landet
        country_lower = country.lower()
        target_codes = set()
        
        # Sjekk norske navn i IOC_TO_NAME
        for code, name in IOC_TO_NAME.items():
            if country_lower in name.lower() or country_lower == code.lower():
                target_codes.add(code)
        
        # Sjekk engelske navn
        if not target_codes and country_lower in ENGLISH_TO_IOC:
            target_codes.add(ENGLISH_TO_IOC[country_lower])
        
        if not target_codes:
            # Prøv med koden direkte
            target_codes.add(country.upper())
        
        # Hent wikitext
        resp = requests.get(WIKI_API, params={
            "action": "parse",
            "page": winners_page,
            "prop": "wikitext",
            "format": "json",
        }, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        
        if not wikitext:
            return f"Kunne ikke hente medaljevinnere fra Wikipedia."
        
        # Parse medaljister fra wikitext
        medal_winners = _parse_medal_winners(wikitext, target_codes)
        
        if not medal_winners:
            return f"Ingen medaljevinnere funnet for {country} ennå."
        
        olympics_name = _extract_olympics_name(page_title)
        country_display = IOC_TO_NAME.get(list(target_codes)[0], country)
        
        lines = [f"Medaljevinnere for {country_display} - {olympics_name}:", ""]
        
        medal_emoji = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}
        
        for winner in medal_winners:
            emoji = medal_emoji.get(winner["medal"], "🏅")
            names = ", ".join(winner["athletes"])
            lines.append(f"  {emoji} {winner['sport']} - {winner['event']}: {names}")
        
        # Oppsummering fra vinner-listen
        detail_golds = sum(1 for w in medal_winners if w["medal"] == "gold")
        detail_silvers = sum(1 for w in medal_winners if w["medal"] == "silver")
        detail_bronzes = sum(1 for w in medal_winners if w["medal"] == "bronze")
        
        # Kryss-sjekk med medaljetabellen for nøyaktig totaltall
        # Bruk det norske visningsnavnet for å sikre ⬅️-markør i resultatet
        table_result = get_olympics_medals(top_n=1, country=country_display)
        # Format: " 1. Norge                    3   1   2    6 ⬅️"
        table_match = re.search(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*⬅️", table_result)
        if table_match:
            table_g, table_s, table_b = int(table_match.group(1)), int(table_match.group(2)), int(table_match.group(3))
            table_total = table_g + table_s + table_b
            detail_total = detail_golds + detail_silvers + detail_bronzes
            
            lines.append(f"\nTotalt: {table_g}🥇 {table_s}🥈 {table_b}🥉 = {table_total} medaljer")
            if detail_total < table_total:
                lines.append(f"(Viser {detail_total} av {table_total} - noen øvelser er ikke detaljert ennå)")
        else:
            lines.append(f"\nTotalt fra detaljer: {detail_golds}🥇 {detail_silvers}🥈 {detail_bronzes}🥉 = {detail_golds + detail_silvers + detail_bronzes} medaljer")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Feil ved henting av medaljedetaljer: {e}")
        return f"Kunne ikke hente medaljedetaljer: {e}"


def _parse_medal_winners(wikitext: str, target_codes: set) -> list:
    """Parse medaljevinnere fra Wikipedia 'List of medal winners' wikitext.
    
    Wikitext tabellformat:
    - Rad separator: |-
    - Cell 0: event-navn (med DetailsLink)
    - Cell 1: gull-vinner  (flagIOCmedalist)
    - Cell 2: sølv-vinner
    - Cell 3: bronse-vinner
    """
    medal_types = {1: "gold", 2: "silver", 3: "bronze"}
    current_sport = ""
    winners = []
    row_cells = []
    
    for line in wikitext.split("\n"):
        line = line.strip()
        
        # Sport headers (== Sport ==)
        sport_match = re.match(r"^==([^=]+)==$", line)
        if sport_match:
            current_sport = sport_match.group(1).strip()
            continue
        
        # Ny rad - prosesser forrige
        if line.startswith("|-"):
            if row_cells:
                _process_medal_row(row_cells, current_sport, target_codes, medal_types, winners)
            row_cells = []
            continue
        
        # Samle celler
        if line.startswith("|") and not line.startswith("|}") and not line.startswith("{|"):
            parts = line.split("||")
            row_cells.extend(parts)
    
    # Prosesser siste rad
    if row_cells:
        _process_medal_row(row_cells, current_sport, target_codes, medal_types, winners)
    
    return winners


def _process_medal_row(row_cells: list, sport: str, target_codes: set, medal_types: dict, winners: list):
    """Prosesser en tabellrad og legg til medaljister for target-landet."""
    # Finn event-navn
    event_name = ""
    for cell in row_cells:
        if "DetailsLink" in cell:
            event_match = re.search(r"\|(.+?)(?:<br|$)", cell)
            if event_match:
                event_name = event_match.group(1)
                # Unwrap templates som {{Nowrap|text}} → text (behold innholdet)
                event_name = re.sub(r"{{[^|{}]+\|([^{}]+)}}", r"\1", event_name)
                # Fjern enkle templates uten innhold som {{Something}}
                event_name = re.sub(r"{{[^{}]*}}", "", event_name)
                event_name = re.sub(r"\s*<br\s*/?>.*", "", event_name).strip()
            break
    
    if not event_name:
        return
    
    # Sjekk celle 1 (gull), 2 (sølv), 3 (bronse)
    for cell_idx in range(1, min(4, len(row_cells))):
        cell = row_cells[cell_idx]
        medal_type = medal_types.get(cell_idx, "unknown")
        
        # Finn alle athletes for target-landet i denne cellen
        # Format: flagIOCmedalist|[[name]]|CODE|2026 Winter
        # Eller:  flagIOCmedalist|[[display|name]]|CODE|2026 Winter
        athletes = re.findall(
            r"flagIOCmedalist\|\[\[(?:[^\]|]+\|)?([^\]]+)\]\]\|(\w+)",
            cell
        )
        
        country_athletes = [name for name, code in athletes if code in target_codes]
        
        if country_athletes:
            winners.append({
                "sport": sport,
                "event": event_name,
                "medal": medal_type,
                "athletes": country_athletes,
            })
