#!/usr/bin/env python3
import re

# Simulert e-post data (fra HA)
emails = [
    {
        "subject": "Loggoppsummering siste 24 timer",
        "sender": "no-reply@havindustritilsynet.no",
        "body": "<body><p style='border-style:solid; border-color:#FF0000; border-width:1px; width:100%'><strong>EXTERNAL SENDER </strong></p><div><p class='editor-paragraph'>Hei,<br><br>Her er en oppsummering av loggaktivitet fra systemet de siste 24 timene:<br><br>- Totalt 156 logger registrert<br>- 12 advarsler<br>- 2 feil (begge relatert til database-synkronisering)<br>- Gjennomsnittlig responstid: 245ms<br><br>Vennligst gjennomgå de to feilene i admin-panelet.<br><br>Hilsen<br>Automatisk loggrapportering</p></div></body>",
        "is_read": True
    },
    {
        "subject": "Refresh failed: Planmodell has failed to refresh",
        "sender": "no-reply-powerbi@microsoft.com", 
        "body": "<html><head></head><body><div style='font-family: Segoe UI, sans-serif;'><h2>Power BI Refresh Failed</h2><p>Your dataset <strong>Planmodell</strong> failed to refresh at 2026-01-17 10:30:45 UTC.</p><p><strong>Error details:</strong><br>The remote server returned an error: (401) Unauthorized. Unable to connect to the data source.</p><p>Please check your credentials and try again.</p><p>Best regards,<br>The Power BI Team</p></div></body></html>",
        "is_read": True
    }
]

def clean_html(html):
    """Rens HTML-tags"""
    clean = re.sub(r'<[^>]+>', '', html)
    clean = clean.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&')
    return clean.strip()

# Simuler hva Anda ville sagt
for i, email in enumerate(emails, 1):
    subject = email['subject']
    sender = email['sender']
    body_html = email['body']
    
    clean_body = clean_html(body_html)
    
    # Begrens til 500 tegn
    if len(clean_body) > 500:
        clean_body = clean_body[:500] + "..."
    
    print(f"═══════════════════════════════════════════════════════════")
    print(f"E-POST #{i}")
    print(f"═══════════════════════════════════════════════════════════")
    print(f"Fra: {sender}")
    print(f"Emne: {subject}")
    print(f"\n🦆 HVA ANDA VILLE SAGT:")
    print(f"-----------------------------------------------------------")
    print(f"E-post fra {sender} med emne '{subject}':\n")
    print(clean_body)
    print(f"\n")
