# Anda SMS Relay Server

SMS relay server for routing Twilio webhooks to the correct Anda (Duck) Pi instance. Production hostname: **sms-relay.duckberry.no**.

## Architecture
```
Twilio → sms-relay.duckberry.no (queues SMS) ← Anda Pi (polls every 10s)
```

## How It Works
- **Registration**: Each Anda registers its Twilio number and current IP on startup.
- **Heartbeat**: Anda polls relay every 10 seconds for new messages (also acts as heartbeat).
- **Queuing**: Incoming Twilio webhooks are queued in memory.
- **Polling**: Anda retrieves and clears its message queue on each poll.
- **NAT-friendly**: Works from any network - no port forwarding needed!

## API Endpoints
- **POST /webhook/sms/{twilio_number}**: Receives Twilio webhook and queues message
- **GET /poll/{twilio_number}**: Anda polls for pending messages (also updates heartbeat)
- **POST /register**: Body `{twilio_number, name, ip}` registers an Anda entry
- **POST /unregister**: Body `{twilio_number}` removes an Anda entry
- **GET /status**: Returns registry, queue sizes, and online/offline status
- **GET /health**: Basic health probe

##**Register** (Anda calls this on startup)
```bash
twilio_number="+12025551234"
curl -X POST https://sms-relay.duckberry.no/register \
  -H "Content-Type: application/json" \
  -d '{"twilio_number":"'"${twilio_number}"'","name":"Anda-Oslo","ip":"192.168.1.50"}'
```

- **Poll for messages** (Anda calls this every 10s)
```bash
curl https://sms-relay.duckberry.no/poll/%2B12025551234
# Returns: {"status":"ok","messages":[...],"count":0}
```

- **Simulated Twilio webhook** (for testing)
```bash
curl -X POST "https://sms-relay.duckberry.no/webhook/sms/%2B12025551234" \
  -d "From=%2B4712345678" \
  -d "Body=Test+melding" \
  -d "To=%2B12025551234" \
  -d "MessageSid=SM123"
# Returns: {"status":"queued","duck":"Anda-Oslo","queue_size":1}\
  -d "MessageSid=SM123"
```

## Local Testing
```bash
cd sms-relay
pip install -r requirements.txt
cp .env.example .env  # adjust as needed
python app.py  # serves on http://localhost:8000
```

## Azure Deployment (current)
Target: App Service **duck-sms-relay** in resource group **og-sms-relay-rg** (plan **og-sms-relay-plan**, Linux B1). Custom domain: **sms-relay.duckberry.no**.

```bash
# Login
az login

# Ensure RG + plan
az group create --name og-sms-relay-rg --location norwayeast
az appservice plan create \
  --name og-sms-relay-plan \
  --resource-group og-sms-relay-rg \
  --sku B1 \
  --is-linux

# Create/ensure web app (Python 3.11)
az webapp create \
  --resource-group og-sms-relay-rg \
  --plan og-sms-relay-plan \
  --name duck-sms-relay \
  --runtime "PYTHON:3.11"

# Settings + startup
az webapp config appsettings set \
  --resource-group og-sms-relay-rg \
  --name duck-sms-relay \
  --settings WEBSITES_PORT=8000 SCM_DO_BUILD_DURING_DEPLOYMENT=true
az webapp config set \
  --resource-group og-sms-relay-rg \
  --name duck-sms-relay \
  --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app"

# Package minimal payload (from repo root)
cd sms-relay
zip ../deploy.zip app.py requirements.txt .deployment

# Deploy (oryx build)
az webapp deploy \
  --resource-group og-sms-relay-rg \
  --name duck-sms-relay \
  --src-path ../deploy.zip \
  --type zip

# Custom domain (CNAME sms-relay.duckberry.no -> duck-sms-relay.azurewebsites.net)
az webapp config hostname add \
  --resource-group og-sms-relay-rg \
  --webapp-name duck-sms-relay \
  --hostname sms-relay.duckberry.no

# Optional: Always On
az webapp config set \
  --resource-group og-sms-relay-rg \
  --name duck-sms-relay \
  --always-on true
```

## Twilio Configuration
- Webhook URL per number: `https://sms-relay.duckberry.no/webhook/sms/{twilio_number}`
- Example: number `+12025551234` → webhook `https://sms-relay.duckberry.no/webhook/sms/+12025551234` (POST)

## Anda Pi Integration (automatic)
The `chatgpt_voice.py` service automatically:
1. Registers with relay on startup
2. Polls for messages every 10 seconds
3. Processes incoming SMS via `SMSManager`

No manual configuration needed - just set environment variables:
```bash
# In .env
TWILIO_NUMBER=+12025551234
DUCK_NAME=Samantha
SMS_RELAY_URL=https://sms-relay.duckberry.no/register
```

## Monitoring & Troubleshooting
- Logs: `az webapp log tail --resource-group og-sms-relay-rg --name duck-sms-relay`
- Health: `https://sms-relay.duckberry.no/health`
- Registry: `https://sms-relay.duckberry.no/status`
- If SMS not delivered: verify Twilio webhook URL, check `/status` for online status, inspect App Service logs.

## Future Improvements
- Twilio signature validation
- Rate limiting on webhooks
- Auth token for /register
- Redis-backed registry for multi-instance scaling
