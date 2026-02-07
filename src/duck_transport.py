"""
Duck Transport Module
Henter avganger og reiseforslag fra Entur API.
Gratis, ingen API-nøkkel nødvendig (bare ET-Client-Name header).
"""

import requests
from datetime import datetime
from typing import Optional


ENTUR_GEOCODER_URL = 'https://api.entur.io/geocoder/v1/autocomplete'
ENTUR_GRAPHQL_URL = 'https://api.entur.io/journey-planner/v3/graphql'

HEADERS = {
    'Content-Type': 'application/json',
    'ET-Client-Name': 'chatgpt-duck-samantha',
}

# Norsk oversettelse av transporttype
TRANSPORT_MODE_NO = {
    'bus': '🚌 Buss',
    'tram': '🚋 Trikk',
    'metro': '🚇 T-bane',
    'rail': '🚆 Tog',
    'water': '⛴️ Båt',
    'air': '✈️ Fly',
    'coach': '🚍 Ekspressbuss',
    'funicular': '🚡 Kabelbane',
}


def _find_stop(query: str) -> Optional[dict]:
    """
    Søk etter holdeplass/stasjon via Entur geocoder.

    Returns:
        dict med 'id', 'name', 'locality' eller None
    """
    try:
        params = {
            'text': query,
            'lang': 'no',
            'layers': 'venue',
            'size': 1,
        }
        response = requests.get(ENTUR_GEOCODER_URL, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()

        data = response.json()
        features = data.get('features', [])

        if not features:
            return None

        props = features[0]['properties']
        return {
            'id': props.get('id', ''),
            'name': props.get('name', ''),
            'locality': props.get('locality', ''),
            'label': props.get('label', ''),
        }
    except Exception as e:
        print(f"⚠️ Entur geocoder feil: {e}", flush=True)
        return None


def _format_time(iso_time: str) -> str:
    """Formater ISO-tid til HH:MM"""
    try:
        dt = datetime.fromisoformat(iso_time)
        return dt.strftime('%H:%M')
    except Exception:
        return iso_time


def _minutes_until(iso_time: str) -> str:
    """Beregn minutter til avgang"""
    try:
        dt = datetime.fromisoformat(iso_time)
        now = datetime.now(dt.tzinfo)
        diff = dt - now
        minutes = int(diff.total_seconds() / 60)
        if minutes <= 0:
            return "nå"
        elif minutes == 1:
            return "1 min"
        else:
            return f"{minutes} min"
    except Exception:
        return ""


def get_departures(stop_name: str, count: int = 8, transport_mode: Optional[str] = None) -> str:
    """
    Hent neste avganger fra en holdeplass/stasjon.

    Args:
        stop_name: Navn på holdeplass (f.eks. 'Jernbanetorget', 'Grønland', 'Oslo S')
        count: Antall avganger (default 8, max 20)
        transport_mode: Filtrer på transporttype (bus, tram, metro, rail, water) - valgfritt

    Returns:
        Formatert streng med avganger
    """
    # Finn holdeplass
    stop = _find_stop(stop_name)
    if not stop:
        return f"❌ Fant ingen holdeplass med navn '{stop_name}'. Prøv et mer presist navn."

    stop_id = stop['id']
    stop_label = stop['label']

    # Bygg GraphQL-query
    count = min(count, 20)

    # Filtrer på transporttype hvis angitt
    whitelist = ""
    if transport_mode:
        mode_map = {
            'buss': 'bus', 'bus': 'bus',
            'trikk': 'tram', 'tram': 'tram',
            'tbane': 'metro', 't-bane': 'metro', 'metro': 'metro',
            'tog': 'rail', 'rail': 'rail', 'jernbane': 'rail',
            'båt': 'water', 'ferge': 'water', 'water': 'water',
        }
        resolved = mode_map.get(transport_mode.lower(), transport_mode.lower())
        whitelist = f', whiteListedModes: [{resolved}]'

    query = f"""{{
        stopPlace(id: "{stop_id}") {{
            name
            estimatedCalls(timeRange: 7200, numberOfDepartures: {count}{whitelist}) {{
                expectedDepartureTime
                aimedDepartureTime
                realtime
                destinationDisplay {{
                    frontText
                }}
                serviceJourney {{
                    line {{
                        publicCode
                        transportMode
                    }}
                }}
            }}
        }}
    }}"""

    try:
        print(f"🚌 Henter avganger fra {stop_label} ({stop_id})", flush=True)
        response = requests.post(
            ENTUR_GRAPHQL_URL,
            json={'query': query},
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        stop_data = data.get('data', {}).get('stopPlace')

        if not stop_data:
            return f"❌ Ingen data for holdeplass {stop_label}"

        calls = stop_data.get('estimatedCalls', [])
        if not calls:
            return f"Ingen avganger fra {stop_label} de neste 2 timene."

        # Formater resultat
        results = [f"🚏 Avganger fra {stop_label}:\n"]

        for call in calls:
            departure = call.get('expectedDepartureTime', '')
            aimed = call.get('aimedDepartureTime', '')
            realtime = call.get('realtime', False)
            destination = call.get('destinationDisplay', {}).get('frontText', '?')
            line = call.get('serviceJourney', {}).get('line', {})
            line_code = line.get('publicCode', '?')
            mode = line.get('transportMode', 'bus')

            time_str = _format_time(departure)
            minutes = _minutes_until(departure)
            mode_str = TRANSPORT_MODE_NO.get(mode, mode)

            # Sjekk forsinkelse
            delay_str = ""
            if aimed and departure and aimed != departure:
                aimed_time = _format_time(aimed)
                delay_str = f" (planlagt {aimed_time})"

            rt_str = "⏱️" if realtime else "📅"

            results.append(
                f"  {rt_str} {time_str} ({minutes}) — {mode_str} {line_code} → {destination}{delay_str}"
            )

        results.append(f"\n⏱️ = sanntid, 📅 = ruteplan")

        formatted = "\n".join(results)
        print(f"✅ Hentet {len(calls)} avganger fra {stop_label}", flush=True)
        return formatted

    except requests.Timeout:
        return "❌ Entur svarte ikke (timeout)"
    except requests.RequestException as e:
        return f"❌ Feil ved henting av avganger: {str(e)}"
    except Exception as e:
        print(f"❌ Uventet feil i get_departures: {e}", flush=True)
        return f"❌ Kunne ikke hente avganger: {str(e)}"


def plan_journey(from_place: str, to_place: str, count: int = 3) -> str:
    """
    Planlegg en reise mellom to steder.

    Args:
        from_place: Avgangssted (holdeplass, adresse, eller sted)
        to_place: Destinasjon
        count: Antall reiseforslag (default 3, max 5)

    Returns:
        Formatert streng med reiseforslag
    """
    from_stop = _find_stop(from_place)
    to_stop = _find_stop(to_place)

    if not from_stop:
        return f"❌ Fant ingen holdeplass/sted for '{from_place}'"
    if not to_stop:
        return f"❌ Fant ingen holdeplass/sted for '{to_place}'"

    count = min(count, 5)

    query = f"""{{
        trip(
            from: {{place: "{from_stop['id']}"}},
            to: {{place: "{to_stop['id']}"}},
            numTripPatterns: {count}
        ) {{
            tripPatterns {{
                duration
                startTime
                endTime
                legs {{
                    mode
                    fromPlace {{
                        name
                    }}
                    toPlace {{
                        name
                    }}
                    expectedStartTime
                    expectedEndTime
                    line {{
                        publicCode
                        name
                    }}
                    distance
                }}
            }}
        }}
    }}"""

    try:
        print(f"🗺️ Planlegger reise: {from_stop['label']} → {to_stop['label']}", flush=True)
        response = requests.post(
            ENTUR_GRAPHQL_URL,
            json={'query': query},
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()

        data = response.json()
        patterns = data.get('data', {}).get('trip', {}).get('tripPatterns', [])

        if not patterns:
            return f"Fant ingen reiser fra {from_stop['name']} til {to_stop['name']}"

        results = [f"🗺️ Reise: {from_stop['name']} → {to_stop['name']}\n"]

        for i, pattern in enumerate(patterns, 1):
            start = _format_time(pattern.get('startTime', ''))
            end = _format_time(pattern.get('endTime', ''))
            duration_sec = pattern.get('duration', 0)
            duration_min = duration_sec // 60

            results.append(f"--- Forslag {i}: {start} → {end} ({duration_min} min) ---")

            for leg in pattern.get('legs', []):
                mode = leg.get('mode', 'foot').lower()
                from_name = leg.get('fromPlace', {}).get('name', '?')
                to_name = leg.get('toPlace', {}).get('name', '?')
                leg_start = _format_time(leg.get('expectedStartTime', ''))
                leg_end = _format_time(leg.get('expectedEndTime', ''))
                line = leg.get('line')

                if mode == 'foot':
                    distance = leg.get('distance', 0)
                    dist_str = f" ({int(distance)}m)" if distance else ""
                    results.append(f"  🚶 {leg_start}-{leg_end} Gå{dist_str}: {from_name} → {to_name}")
                else:
                    mode_str = TRANSPORT_MODE_NO.get(mode, mode)
                    line_code = line.get('publicCode', '?') if line else '?'
                    results.append(f"  {mode_str} {line_code} {leg_start}-{leg_end}: {from_name} → {to_name}")

            results.append("")

        formatted = "\n".join(results)
        print(f"✅ Fant {len(patterns)} reiseforslag", flush=True)
        return formatted

    except requests.Timeout:
        return "❌ Entur svarte ikke (timeout)"
    except requests.RequestException as e:
        return f"❌ Feil ved reiseplanlegging: {str(e)}"
    except Exception as e:
        print(f"❌ Uventet feil i plan_journey: {e}", flush=True)
        return f"❌ Kunne ikke planlegge reise: {str(e)}"
