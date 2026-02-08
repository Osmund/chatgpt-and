"""
Premier League data fra football-data.org API
Gir tabell, resultater og kommende kamper for Samantha/Anda.
"""

import requests
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

API_KEY = "2ab2b1cb67a84bcf991b6f1f0c8186e3"
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}

# Korte norske lagsnavn for TTS-vennlig output
TEAM_NAMES_NO = {
    "Arsenal FC": "Arsenal",
    "Aston Villa FC": "Aston Villa",
    "AFC Bournemouth": "Bournemouth",
    "Brentford FC": "Brentford",
    "Brighton & Hove Albion FC": "Brighton",
    "Chelsea FC": "Chelsea",
    "Crystal Palace FC": "Crystal Palace",
    "Everton FC": "Everton",
    "Fulham FC": "Fulham",
    "Ipswich Town FC": "Ipswich",
    "Leeds United FC": "Leeds",
    "Leicester City FC": "Leicester",
    "Liverpool FC": "Liverpool",
    "Manchester City FC": "Man City",
    "Manchester United FC": "Man United",
    "Newcastle United FC": "Newcastle",
    "Nottingham Forest FC": "Nottingham Forest",
    "Southampton FC": "Southampton",
    "Tottenham Hotspur FC": "Tottenham",
    "West Ham United FC": "West Ham",
    "Wolverhampton Wanderers FC": "Wolves",
}


def _short_name(full_name: str) -> str:
    """Konverter fullt lagnavn til kort TTS-vennlig versjon."""
    return TEAM_NAMES_NO.get(full_name, full_name)


def get_pl_standings(top_n: int = 20) -> str:
    """Hent Premier League-tabellen.
    
    Args:
        top_n: Antall lag å vise (default alle 20)
    
    Returns:
        Formatert tabellstreng for AI-kontekst
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/competitions/PL/standings",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        season = data.get("season", {})
        matchday = season.get("currentMatchday", "?")
        
        standings = data["standings"]
        # Finn TOTAL-tabellen (ikke HOME/AWAY)
        total = next(s for s in standings if s["type"] == "TOTAL")
        table = total["table"][:top_n]
        
        lines = [f"Premier League tabell (runde {matchday}):", ""]
        lines.append(f"{'#':>2}  {'Lag':<20} {'K':>3} {'V':>3} {'U':>3} {'T':>3} {'MF':>4} {'P':>3}")
        lines.append("-" * 50)
        
        for entry in table:
            pos = entry["position"]
            name = _short_name(entry["team"]["name"])
            played = entry["playedGames"]
            won = entry["won"]
            draw = entry["draw"]
            lost = entry["lost"]
            gd = entry["goalDifference"]
            points = entry["points"]
            
            gd_str = f"+{gd}" if gd > 0 else str(gd)
            lines.append(f"{pos:>2}. {name:<20} {played:>3} {won:>3} {draw:>3} {lost:>3} {gd_str:>4} {points:>3}")
        
        return "\n".join(lines)
        
    except requests.RequestException as e:
        logger.error(f"Feil ved henting av PL-tabell: {e}")
        return f"Kunne ikke hente Premier League-tabellen: {e}"
    except Exception as e:
        logger.error(f"Feil ved parsing av PL-tabell: {e}")
        return f"Feil ved behandling av tabelldata: {e}"


def get_pl_matches(match_type: str = "recent", count: int = 10) -> str:
    """Hent PL-kamper (resultater, kommende, eller spesifikt lag).
    
    Args:
        match_type: "recent" (siste resultater), "upcoming" (kommende), 
                    eller et lagnavn for å se det lagets kamper
        count: Antall kamper å vise
    
    Returns:
        Formatert kampstreng for AI-kontekst
    """
    try:
        if match_type == "recent":
            return _get_recent_results(count)
        elif match_type == "upcoming":
            return _get_upcoming_matches(count)
        else:
            return _get_team_matches(match_type, count)
    except requests.RequestException as e:
        logger.error(f"Feil ved henting av PL-kamper: {e}")
        return f"Kunne ikke hente kamper: {e}"
    except Exception as e:
        logger.error(f"Feil ved parsing av PL-kamper: {e}")
        return f"Feil ved behandling av kampdata: {e}"


def _get_recent_results(count: int) -> str:
    """Hent siste spilte kamper."""
    resp = requests.get(
        f"{BASE_URL}/competitions/PL/matches",
        headers=HEADERS,
        params={"status": "FINISHED", "limit": count},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    
    matches = data.get("matches", [])
    # Sorter etter dato, nyeste først
    matches.sort(key=lambda m: m["utcDate"], reverse=True)
    matches = matches[:count]
    
    if not matches:
        return "Ingen nylige resultater funnet."
    
    lines = ["Siste Premier League-resultater:", ""]
    
    current_date = None
    for match in matches:
        date = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        date_str = date.strftime("%d. %b")
        
        if date_str != current_date:
            current_date = date_str
            lines.append(f"📅 {date_str}:")
        
        home = _short_name(match["homeTeam"]["name"])
        away = _short_name(match["awayTeam"]["name"])
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home", "?")
        away_goals = score.get("away", "?")
        
        lines.append(f"  {home} {home_goals}-{away_goals} {away}")
    
    return "\n".join(lines)


def _get_upcoming_matches(count: int) -> str:
    """Hent kommende kamper."""
    resp = requests.get(
        f"{BASE_URL}/competitions/PL/matches",
        headers=HEADERS,
        params={"status": "SCHEDULED,TIMED", "limit": count},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    
    matches = data.get("matches", [])
    matches.sort(key=lambda m: m["utcDate"])
    matches = matches[:count]
    
    if not matches:
        return "Ingen kommende kamper funnet."
    
    lines = ["Kommende Premier League-kamper:", ""]
    
    current_date = None
    for match in matches:
        date = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        date_str = date.strftime("%d. %b")
        time_str = date.strftime("%H:%M")
        
        if date_str != current_date:
            current_date = date_str
            lines.append(f"📅 {date_str}:")
        
        home = _short_name(match["homeTeam"]["name"])
        away = _short_name(match["awayTeam"]["name"])
        
        lines.append(f"  {home} vs {away} kl. {time_str}")
    
    return "\n".join(lines)


def _get_team_matches(team_name: str, count: int) -> str:
    """Hent kamper for et spesifikt lag."""
    # Finn lag-ID
    team_name_lower = team_name.lower()
    
    # Søk i alle kjente lag
    team_id = None
    for full_name, short_name in TEAM_NAMES_NO.items():
        if (team_name_lower in full_name.lower() or 
            team_name_lower in short_name.lower()):
            # Hent lag-ID fra standings
            resp = requests.get(
                f"{BASE_URL}/competitions/PL/standings",
                headers=HEADERS,
                timeout=10
            )
            resp.raise_for_status()
            standings = resp.json()["standings"]
            total = next(s for s in standings if s["type"] == "TOTAL")
            for entry in total["table"]:
                if entry["team"]["name"] == full_name:
                    team_id = entry["team"]["id"]
                    team_display = short_name
                    break
            if team_id:
                break
    
    if not team_id:
        return f"Fant ikke laget '{team_name}' i Premier League."
    
    # Hent lagets kamper
    resp = requests.get(
        f"{BASE_URL}/teams/{team_id}/matches",
        headers=HEADERS,
        params={"competitions": "PL", "limit": count},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    
    matches = data.get("matches", [])
    
    if not matches:
        return f"Ingen kamper funnet for {team_display}."
    
    lines = [f"Kamper for {team_display}:", ""]
    
    for match in matches:
        date = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
        date_str = date.strftime("%d. %b")
        
        home = _short_name(match["homeTeam"]["name"])
        away = _short_name(match["awayTeam"]["name"])
        status = match["status"]
        
        if status == "FINISHED":
            score = match.get("score", {}).get("fullTime", {})
            home_goals = score.get("home", "?")
            away_goals = score.get("away", "?")
            lines.append(f"  {date_str}: {home} {home_goals}-{away_goals} {away}")
        else:
            time_str = date.strftime("%H:%M")
            lines.append(f"  {date_str}: {home} vs {away} kl. {time_str}")
    
    return "\n".join(lines)
