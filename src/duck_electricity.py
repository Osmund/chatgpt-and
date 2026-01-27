"""
Duck Electricity Price Module
Henter strømpriser fra hvakosterstrommen.no API og beregner faktisk forbrukerpris
med strømstøtte og mva.
"""

import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Strømstøtte (2026): 90% av pris over 0.73 kr/kWh
STROMSTOETTE_THRESHOLD = float(os.getenv('ELECTRICITY_SUBSIDY_THRESHOLD', '0.73'))  # kr/kWh
STROMSTOETTE_PERCENTAGE = float(os.getenv('ELECTRICITY_SUBSIDY_PERCENTAGE', '0.90'))  # 90%
MVA_RATE = float(os.getenv('ELECTRICITY_VAT_RATE', '0.25'))  # 25%
NORGESPRIS = float(os.getenv('ELECTRICITY_NORGESPRIS', '0.50'))  # kr/kWh inkl. mva

# Prisområder
REGIONS = {
    'NO1': 'Oslo / Øst-Norge',
    'NO2': 'Kristiansand / Sør-Norge',
    'NO3': 'Trondheim / Midt-Norge',
    'NO4': 'Tromsø / Nord-Norge',
    'NO5': 'Bergen / Vest-Norge'
}

DEFAULT_REGION = os.getenv('ELECTRICITY_REGION', 'NO2')


def calculate_consumer_price(spot_price: float, include_subsidy: bool = True) -> Dict:
    """
    Beregn faktisk forbrukerpris med strømstøtte og mva.
    
    Args:
        spot_price: Spotpris uten mva (kr/kWh)
        include_subsidy: Om strømstøtte skal inkluderes
    
    Returns:
        Dict med prisdetaljer
    """
    # Beregn strømstøtte
    subsidy = 0.0
    if include_subsidy and spot_price > STROMSTOETTE_THRESHOLD:
        subsidy = (spot_price - STROMSTOETTE_THRESHOLD) * STROMSTOETTE_PERCENTAGE
    
    # Pris etter strømstøtte (før mva)
    price_after_subsidy = spot_price - subsidy
    
    # Legg til mva
    final_price = price_after_subsidy * (1 + MVA_RATE)
    
    return {
        'spot_price': round(spot_price, 2),
        'subsidy': round(subsidy, 2),
        'price_after_subsidy': round(price_after_subsidy, 2),
        'final_price': round(final_price, 2),
        'mva': round(price_after_subsidy * MVA_RATE, 2)
    }


def fetch_prices(region: str = DEFAULT_REGION, date: Optional[datetime] = None) -> Optional[List[Dict]]:
    """
    Hent strømpriser fra API.
    
    Args:
        region: Prisområde (NO1-NO5)
        date: Dato å hente priser for (default: i dag)
    
    Returns:
        Liste med priser per time, eller None ved feil
    """
    if date is None:
        date = datetime.now()
    
    # Format: YYYY/MM-DD_REGION.json
    date_str = date.strftime("%Y/%m-%d")
    url = f"https://www.hvakosterstrommen.no/api/v1/prices/{date_str}_{region}.json"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Feil ved henting av strømpriser: {e}", flush=True)
        return None


def get_current_price(region: str = DEFAULT_REGION, include_subsidy: bool = True) -> Optional[Dict]:
    """
    Hent nåværende strømpris.
    
    Args:
        region: Prisområde (NO1-NO5)
        include_subsidy: Om strømstøtte skal inkluderes
    
    Returns:
        Dict med prisinfo for nåværende time
    """
    prices = fetch_prices(region)
    if not prices:
        return None
    
    now = datetime.now()
    current_hour = now.hour
    
    # Finn pris for nåværende time
    for price_data in prices:
        time_start = datetime.fromisoformat(price_data['time_start'])
        if time_start.hour == current_hour:
            spot_price = price_data['NOK_per_kWh']
            calc = calculate_consumer_price(spot_price, include_subsidy)
            
            return {
                'time': time_start.strftime('%H:%M'),
                'hour': current_hour,
                **calc,
                'region': region,
                'region_name': REGIONS.get(region, region)
            }
    
    return None


def get_daily_stats(region: str = DEFAULT_REGION, include_subsidy: bool = True) -> Optional[Dict]:
    """
    Hent statistikk for dagens strømpriser.
    
    Args:
        region: Prisområde (NO1-NO5)
        include_subsidy: Om strømstøtte skal inkluderes
    
    Returns:
        Dict med min, max, avg, current
    """
    prices = fetch_prices(region)
    if not prices:
        return None
    
    # Beregn forbrukerpriser for alle timer
    consumer_prices = []
    for price_data in prices:
        spot = price_data['NOK_per_kWh']
        calc = calculate_consumer_price(spot, include_subsidy)
        time_start = datetime.fromisoformat(price_data['time_start'])
        consumer_prices.append({
            'hour': time_start.hour,
            'time': time_start.strftime('%H:%M'),
            'final_price': calc['final_price'],
            'spot_price': calc['spot_price']
        })
    
    # Finn min, max, avg
    prices_only = [p['final_price'] for p in consumer_prices]
    avg_price = sum(prices_only) / len(prices_only)
    
    min_entry = min(consumer_prices, key=lambda x: x['final_price'])
    max_entry = max(consumer_prices, key=lambda x: x['final_price'])
    
    # Finn nåværende time
    current_hour = datetime.now().hour
    current_entry = next((p for p in consumer_prices if p['hour'] == current_hour), None)
    
    return {
        'region': region,
        'region_name': REGIONS.get(region, region),
        'date': datetime.now().strftime('%d.%m.%Y'),
        'average': round(avg_price, 2),
        'min': {
            'price': min_entry['final_price'],
            'time': min_entry['time'],
            'hour': min_entry['hour']
        },
        'max': {
            'price': max_entry['final_price'],
            'time': max_entry['time'],
            'hour': max_entry['hour']
        },
        'current': current_entry,
        'all_prices': consumer_prices
    }


def get_cheapest_hours(region: str = DEFAULT_REGION, count: int = 3, include_subsidy: bool = True) -> Optional[List[Dict]]:
    """
    Finn de billigste timene i dag.
    
    Args:
        region: Prisområde (NO1-NO5)
        count: Antall timer å returnere
        include_subsidy: Om strømstøtte skal inkluderes
    
    Returns:
        Liste med de billigste timene
    """
    stats = get_daily_stats(region, include_subsidy)
    if not stats:
        return None
    
    # Sorteretter pris
    sorted_prices = sorted(stats['all_prices'], key=lambda x: x['final_price'])
    
    return sorted_prices[:count]


def get_price_advice(region: str = DEFAULT_REGION) -> Optional[str]:
    """
    Generer råd om når det er lurt å bruke strøm.
    
    Args:
        region: Prisområde (NO1-NO5)
    
    Returns:
        Tekstlig råd om strømbruk
    """
    stats = get_daily_stats(region)
    if not stats:
        return None
    
    current = stats['current']
    if not current:
        return None
    
    min_price = stats['min']
    max_price = stats['max']
    avg_price = stats['average']
    current_price = current['final_price']
    
    # Generer råd basert på nåværende pris
    if current_price <= min_price['price'] * 1.1:  # Innenfor 10% av billigste
        advice = f"⚡ Strømmen er billig nå! Akkurat nå koster strømmen {current_price:.2f} kr/kWh, som er nær dagens laveste pris. God tid å bruke strøm."
    elif current_price >= max_price['price'] * 0.9:  # Innenfor 10% av dyreste
        advice = f"💸 Strømmen er dyr nå. {current_price:.2f} kr/kWh er nær dagens høyeste pris ({max_price['price']:.2f} kr). Vent til senere hvis mulig."
    elif current_price > avg_price:
        advice = f"📊 Strømmen er litt dyr nå ({current_price:.2f} kr/kWh). Dagens snitt er {avg_price:.2f} kr. Billigste time er kl {min_price['time']}."
    else:
        advice = f"✅ Strømmen er rimelig nå ({current_price:.2f} kr/kWh), under dagens snitt på {avg_price:.2f} kr."
    
    return advice


def calculate_norgespris_savings(region: str = DEFAULT_REGION) -> Optional[Dict]:
    """
    Beregner besparelse med Norgespris vs spotpris.
    
    Args:
        region: Strømregion (NO1-NO5)
    
    Returns:
        Dict med sammenligning og besparelsesinformasjon
    """
    try:
        current = get_current_price(region)
        daily = get_daily_stats(region)
        
        if not current or not daily:
            return None
        
        spot_price = current['final_price']
        savings_now = spot_price - NORGESPRIS
        
        avg_spot = daily['average']
        avg_savings = avg_spot - NORGESPRIS
        
        # Beregn månedlig besparelse (hent fra env eller bruk 300 kWh/måned)
        monthly_kwh = int(os.getenv('ELECTRICITY_MONTHLY_KWH', '300'))
        monthly_savings = avg_savings * monthly_kwh
        
        return {
            'norgespris': NORGESPRIS,
            'spot_now': spot_price,
            'savings_now': savings_now,
            'spot_average': avg_spot,
            'avg_savings': avg_savings,
            'monthly_savings': monthly_savings,
            'monthly_kwh': monthly_kwh,
            'is_saving': savings_now > 0
        }
    except Exception as e:
        print(f"Feil ved beregning av Norgespris-besparelse: {e}")
        return None


def format_price_response(timeframe: str = 'now', region: str = DEFAULT_REGION) -> str:
    """
    Formater strømpris-svar for AI assistant.
    
    Args:
        timeframe: 'now', 'today', 'cheapest', 'advice', 'norgespris'
        region: Prisområde
    
    Returns:
        Formatert tekstsvar
    """
    if timeframe == 'now':
        current = get_current_price(region)
        if not current:
            return "❌ Kunne ikke hente strømprisen akkurat nå. Prøv igjen senere."
        
        return f"💡 Strømprisen akkurat nå er {current['final_price']:.2f} kr/kWh (inkl. strømstøtte og mva). Spotpris: {current['spot_price']:.2f} kr."
    
    elif timeframe == 'today':
        stats = get_daily_stats(region)
        if not stats:
            return "❌ Kunne ikke hente dagens strømpriser. Prøv igjen senere."
        
        current = stats['current']
        current_text = f"Akkurat nå: {current['final_price']:.2f} kr/kWh. " if current else ""
        
        return f"""📊 Strømpriser i dag ({stats['region_name']}):
{current_text}Snitt: {stats['average']:.2f} kr/kWh
⬇️ Billigst: {stats['min']['price']:.2f} kr kl {stats['min']['time']}
⬆️ Dyrest: {stats['max']['price']:.2f} kr kl {stats['max']['time']}

(Priser inkluderer strømstøtte og mva)"""
    
    elif timeframe == 'cheapest':
        cheapest = get_cheapest_hours(region, count=3)
        if not cheapest:
            return "❌ Kunne ikke hente strømpriser."
        
        lines = ["🕐 De 3 billigste timene i dag:"]
        for i, hour in enumerate(cheapest, 1):
            lines.append(f"{i}. Kl {hour['time']}: {hour['final_price']:.2f} kr/kWh")
        
        return "\n".join(lines)
    
    elif timeframe == 'advice':
        advice = get_price_advice(region)
        if not advice:
            return "❌ Kunne ikke generere strømråd."
        return advice
    
    elif timeframe == 'norgespris':
        savings = calculate_norgespris_savings(region)
        if not savings:
            return "❌ Kunne ikke beregne Norgespris-besparelse akkurat nå."
        
        spot_now = savings['spot_now']
        savings_now = savings['savings_now']
        avg_savings = savings['avg_savings']
        monthly = savings['monthly_savings']
        
        if savings_now > 0:
            # Du sparer penger med Norgespris
            response = f"💰 Med Norgespris (50 øre/kWh) sparer du penger!\n\n"
            response += f"Spotpris akkurat nå: {spot_now:.2f} kr/kWh\n"
            response += f"Norgespris: {NORGESPRIS:.2f} kr/kWh\n"
            response += f"✅ Du sparer {savings_now:.2f} kr per kWh akkurat nå!\n\n"
            response += f"📊 Dagens snitt: {savings['spot_average']:.2f} kr/kWh\n"
            response += f"Gjennomsnittlig besparelse: {avg_savings:.2f} kr/kWh\n\n"
            
            if monthly > 0:
                response += f"💵 Estimert månedlig besparelse: {monthly:.0f} kr (ved {savings['monthly_kwh']} kWh/måned)"
            
            return response
        else:
            # Spotpris er billigere
            response = f"⚠️ Spotpris er billigere enn Norgespris akkurat nå:\n\n"
            response += f"Spotpris nå: {spot_now:.2f} kr/kWh\n"
            response += f"Norgespris: {NORGESPRIS:.2f} kr/kWh\n"
            response += f"Spotpris er {abs(savings_now):.2f} kr billigere per kWh.\n\n"
            response += f"Men over hele dagen: Spotpris-snitt er {savings['spot_average']:.2f} kr/kWh.\n"
            
            if avg_savings > 0:
                response += f"✅ Norgespris er fortsatt {avg_savings:.2f} kr billigere i snitt!"
            else:
                response += f"Spotpris er {abs(avg_savings):.2f} kr billigere i snitt i dag."
            
            return response
    
    return "❌ Ugyldig forespørsel. Bruk 'now', 'today', 'cheapest', 'advice' eller 'norgespris'."


# Test hvis kjørt direkte
if __name__ == "__main__":
    print("🔌 Testing strømpris-modul...\n")
    
    print("1. Nåværende pris:")
    current = get_current_price()
    if current:
        print(f"   {current['final_price']:.2f} kr/kWh (inkl. alt)")
    
    print("\n2. Dagens statistikk:")
    stats = get_daily_stats()
    if stats:
        print(f"   Snitt: {stats['average']:.2f} kr")
        print(f"   Min: {stats['min']['price']:.2f} kr kl {stats['min']['time']}")
        print(f"   Max: {stats['max']['price']:.2f} kr kl {stats['max']['time']}")
    
    print("\n3. Billigste timer:")
    cheapest = get_cheapest_hours(count=3)
    if cheapest:
        for i, hour in enumerate(cheapest, 1):
            print(f"   {i}. Kl {hour['time']}: {hour['final_price']:.2f} kr")
    
    print("\n4. Råd:")
    advice = get_price_advice()
    if advice:
        print(f"   {advice}")
