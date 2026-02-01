# Prusa Connect Integrasjon 🖨️

Anda kan nå overvåke 3D-printeren din via Prusa Connect! Du kan spørre om status og få varsler når print er ferdig.

## Oppsett

### 1. Få API Token fra Prusa Connect

1. Gå til [https://connect.prusa3d.com/](https://connect.prusa3d.com/)
2. Logg inn med Prusa-kontoen din
3. Klikk på din profil (øverst til høyre) → **API Keys**
4. Klikk **Create new API key**
5. Gi den et navn (f.eks. "Anda Duck Assistant")
6. Kopier API key (lagre den trygt!)

### 2. Finn Printer UUID

1. Gå til Prusa Connect dashboard
2. Åpne printeren din
3. UUID finner du i URL-en: `https://connect.prusa3d.com/printer/<UUID>`
4. Eller gå til **Settings** → **Printer Info** → **UUID**

### 3. Legg til i .env

Åpne `/home/admog/Code/chatgpt-and/.env` og legg til:

```bash
# Prusa Connect API
PRUSA_API_TOKEN=your_api_token_here
PRUSA_PRINTER_UUID=your_printer_uuid_here
```

### 4. Restart Anda

```bash
sudo systemctl restart chatgpt-duck.service
```

## Bruk

### Spørre om status

- "Hvordan går det med printen?"
- "Sjekk 3D-printeren"
- "Er printen ferdig?"

### Proaktive varsler

Når printen blir ferdig, vil Anda automatisk si:
> "🖨️ 3D-printen din er ferdig! [navn på fil] er klar til å plukkes opp."

Dette fungerer også når Anda er i sleep mode!

## Status-eksempler

**Under printing:**
> "Printeren holder på med 'benchy_v2.gcode' og er 47% ferdig. Estimert 2 timer og 15 minutter igjen. Nozzle er 215°C og bed er 60°C."

**Ferdig:**
> "Printen er ferdig! 'benchy_v2.gcode' er klar til å plukkes opp."

**Idle:**
> "Printeren står stille akkurat nå."

**Feil:**
> "Det ser ut som printeren har møtt en feil. Sjekk skjermen din!"

## Feilsøking

### "3D-printeren er ikke konfigurert"

- Sjekk at både `PRUSA_API_TOKEN` og `PRUSA_PRINTER_UUID` er satt i `.env`
- Restart tjenesten: `sudo systemctl restart chatgpt-duck.service`

### "Kunne ikke hente status fra 3D-printeren"

- Sjekk internettforbindelsen
- Sjekk at printeren er online i Prusa Connect
- Verifiser at API token er gyldig (ikke utløpt)
- Sjekk logs: `journalctl -u chatgpt-duck.service -n 50`

### Ingen varsler når printen er ferdig

- Sjekk at overvåkning startet ved boot: `journalctl -u chatgpt-duck.service | grep "3D printer monitoring"`
- Sjekk at det ikke er feil i logs

## API Detaljer

Anda bruker [Prusa Connect REST API v1](https://connect.prusa3d.com/docs/api/):

- **Endpoint:** `https://connect.prusa3d.com/c/snapshot`
- **Auth:** Bearer token (PRUSA_API_TOKEN)
- **Polling:** Hver 60. sekund når print er aktiv
- **States:** IDLE, PRINTING, FINISHED, STOPPED, ERROR

## Personvern

- API token lagres lokalt i `.env` (les-kun for root)
- Ingen data sendes til tredjepart
- Kun status-polling, ingen endringer til printeren
