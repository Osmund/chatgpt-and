"""
Duckberry SMS Relay Server
Routes Twilio SMS webhooks to correct Duck instance based on registry.
Version: 2.0
"""
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Registry: {twilio_number: {name, current_ip, last_heartbeat}}
DUCK_REGISTRY = {}

# Message queue: {twilio_number: [messages]}
MESSAGE_QUEUE = {}

# Duck-to-duck message queue: {duck_name: [messages]}
DUCK_TO_DUCK_QUEUE = {}

# Configuration
HEARTBEAT_TIMEOUT = int(os.getenv('HEARTBEAT_TIMEOUT_MINUTES', 10))
DUCK_WEBHOOK_PATH = '/webhook/sms'
DUCK_PORT = '3000'
MAX_QUEUE_SIZE = 100  # Max messages per duck


@app.route('/webhook/sms/<twilio_number>', methods=['POST'])
def twilio_webhook(twilio_number):
    """
    Receive SMS from Twilio, route to correct Anda Pi.
    Twilio sends: From, Body, To, MessageSid, etc.
    """
    try:
        # Parse Twilio webhook data
        from_number = request.form.get('From')
        message_body = request.form.get('Body')
        to_number = request.form.get('To')
        message_sid = request.form.get('MessageSid')
        
        # MMS support - check for media
        num_media = int(request.form.get('NumMedia', 0))
        media_url = None
        if num_media > 0:
            media_url = request.form.get('MediaUrl0')  # First media item
        
        msg_type = "MMS" if media_url else "SMS"
        print(f"📨 Incoming {msg_type}: {message_sid}")
        print(f"   From: {from_number}")
        print(f"   To: {to_number}")
        print(f"   Body: {message_body[:50] if message_body else '(no text)'}...")
        if media_url:
            print(f"   Media: {media_url}")
        
        # Look up Duck instance by Twilio number
        if to_number not in DUCK_REGISTRY:
            print(f"❌ No Duck registered for {to_number}")
            return jsonify({
                'status': 'error',
                'message': f'No Duck instance registered for {to_number}'
            }), 404
        
        duck = DUCK_REGISTRY[to_number]
        
        # Queue message for Duck to poll
        if to_number not in MESSAGE_QUEUE:
            MESSAGE_QUEUE[to_number] = []
        
        message = {
            'from': from_number,
            'to': to_number,
            'message': message_body,
            'media_url': media_url,  # NEW: MMS support
            'sid': message_sid,
            'timestamp': datetime.now().isoformat(),
            'id': message_sid  # Unique ID for tracking
        }
        
        MESSAGE_QUEUE[to_number].append(message)
        
        # Limit queue size
        if len(MESSAGE_QUEUE[to_number]) > MAX_QUEUE_SIZE:
            MESSAGE_QUEUE[to_number] = MESSAGE_QUEUE[to_number][-MAX_QUEUE_SIZE:]
        
        print(f"✅ SMS queued for {duck['name']} (queue size: {len(MESSAGE_QUEUE[to_number])})")
        
        return jsonify({
            'status': 'queued',
            'duck': duck['name'],
            'queue_size': len(MESSAGE_QUEUE[to_number])
        }), 200
    
    except Exception as e:
        print(f"❌ Error routing SMS: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/register', methods=['POST'])
def register_duck():
    """
    Duck Pi registers on startup and sends heartbeat.
    POST body: {
        "twilio_number": "+12025551234",
        "name": "Duck-Oslo",
        "ip": "192.168.1.50"
    }
    """
    try:
        data = request.json
        twilio_number = data.get('twilio_number')
        name = data.get('name')
        ip = data.get('ip')
        
        if not all([twilio_number, name, ip]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields'
            }), 400
        
        # Update registry
        DUCK_REGISTRY[twilio_number] = {
            'name': name,
            'current_ip': ip,
            'last_heartbeat': datetime.now().isoformat()
        }
        
        print(f"✅ Registered {name} ({twilio_number}) at {ip}")
        
        return jsonify({
            'status': 'registered',
            'name': name,
            'ip': ip,
            'heartbeat_timeout': HEARTBEAT_TIMEOUT
        }), 200
    
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/unregister', methods=['POST'])
def unregister_duck():
    """
    Duck Pi unregisters on shutdown.
    POST body: {"twilio_number": "+12025551234"}
    """
    try:
        data = request.json
        twilio_number = data.get('twilio_number')
        
        if twilio_number in DUCK_REGISTRY:
            duck_name = DUCK_REGISTRY[twilio_number]['name']
            del DUCK_REGISTRY[twilio_number]
            print(f"🔌 Unregistered {duck_name}")
            return jsonify({'status': 'unregistered', 'name': duck_name}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Not registered'}), 404
    
    except Exception as e:
        print(f"❌ Unregister error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/poll/<twilio_number>', methods=['GET'])
def poll_messages(twilio_number):
    """
    Duck polls for new messages.
    Returns all pending messages and clears the queue.
    """
    try:
        # Check if Duck is registered
        if twilio_number not in DUCK_REGISTRY:
            return jsonify({
                'status': 'error',
                'message': 'Not registered'
            }), 404
        
        # Update heartbeat
        DUCK_REGISTRY[twilio_number]['last_heartbeat'] = datetime.now().isoformat()
        
        # Get pending messages
        messages = MESSAGE_QUEUE.get(twilio_number, [])
        
        if messages:
            print(f"📬 {DUCK_REGISTRY[twilio_number]['name']} polling: {len(messages)} message(s)")
            # Clear queue after retrieval
            MESSAGE_QUEUE[twilio_number] = []
        
        return jsonify({
            'status': 'ok',
            'messages': messages,
            'count': len(messages)
        }), 200
    
    except Exception as e:
        print(f"❌ Poll error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/duck/send', methods=['POST'])
def duck_send_message():
    """
    Duck-to-duck messaging (no SMS cost).
    POST body: {
        "from_duck": "samantha",
        "to_duck": "seven",
        "message": "Hello!",
        "media_url": "optional url"
    }
    """
    try:
        data = request.json
        from_duck = data.get('from_duck')
        to_duck = data.get('to_duck')
        message_body = data.get('message')
        media_url = data.get('media_url')
        
        if not all([from_duck, to_duck, message_body]):
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields: from_duck, to_duck, message'
            }), 400
        
        # Initialize queue for recipient duck if needed
        if to_duck not in DUCK_TO_DUCK_QUEUE:
            DUCK_TO_DUCK_QUEUE[to_duck] = []
        
        # Create message
        duck_message = {
            'from_duck': from_duck,
            'to_duck': to_duck,
            'message': message_body,
            'media_url': media_url,
            'timestamp': datetime.now().isoformat(),
            'id': f"duck_{datetime.now().timestamp()}"
        }
        
        DUCK_TO_DUCK_QUEUE[to_duck].append(duck_message)
        
        # Limit queue size
        if len(DUCK_TO_DUCK_QUEUE[to_duck]) > MAX_QUEUE_SIZE:
            DUCK_TO_DUCK_QUEUE[to_duck] = DUCK_TO_DUCK_QUEUE[to_duck][-MAX_QUEUE_SIZE:]
        
        print(f"🦆➡️🦆 Duck message: {from_duck} → {to_duck} (queue: {len(DUCK_TO_DUCK_QUEUE[to_duck])})")
        
        return jsonify({
            'status': 'queued',
            'from': from_duck,
            'to': to_duck,
            'queue_size': len(DUCK_TO_DUCK_QUEUE[to_duck])
        }), 200
    
    except Exception as e:
        print(f"❌ Duck message error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/duck/poll/<duck_name>', methods=['GET'])
def duck_poll_messages(duck_name):
    """
    Duck polls for messages from other ducks.
    Returns all pending duck-to-duck messages and clears the queue.
    """
    try:
        # Get pending duck messages
        messages = DUCK_TO_DUCK_QUEUE.get(duck_name, [])
        
        if messages:
            print(f"🦆📬 {duck_name} polling: {len(messages)} duck message(s)")
            # Clear queue after retrieval
            DUCK_TO_DUCK_QUEUE[duck_name] = []
        
        return jsonify({
            'status': 'ok',
            'messages': messages,
            'count': len(messages)
        }), 200
    
    except Exception as e:
        print(f"❌ Duck poll error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    """
    View current registry status.
    """
    registry_status = {}
    
    for number, duck in DUCK_REGISTRY.items():
        registry_status[number] = {
            'name': duck['name'],
            'ip': duck['current_ip'],
            'last_heartbeat': duck['last_heartbeat'],
            'online': is_duck_online(duck),
            'pending_messages': len(MESSAGE_QUEUE.get(number, [])),
            'pending_duck_messages': len(DUCK_TO_DUCK_QUEUE.get(duck['name'], []))
        }
    
    return jsonify({
        'status': 'ok',
        'registry': registry_status,
        'registered_ducks': len(DUCK_REGISTRY)
    }), 200


@app.route('/health', methods=['GET'])
def health():
    """
    Health check for Azure monitoring.
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'registered_ducks': len(DUCK_REGISTRY)
    }), 200


def is_duck_online(duck):
    """
    Check if Duck Pi is online based on last heartbeat.
    """
    if not duck.get('last_heartbeat'):
        return False
    
    last_heartbeat = datetime.fromisoformat(duck['last_heartbeat'])
    timeout = timedelta(minutes=HEARTBEAT_TIMEOUT)
    
    return datetime.now() - last_heartbeat < timeout


@app.route('/')
def index():
    """
    Simple landing page.
    """
    return """
    <html>
    <head><title>Duckberry SMS Relay</title></head>
    <body>
        <h1>🦆 Duckberry SMS Relay Server</h1>
        <p>Routes Twilio SMS webhooks to correct Duck instance.</p>
        <ul>
            <li><a href="/status">View Registry Status</a></li>
            <li><a href="/health">Health Check</a></li>
        </ul>
        <p>Registered Ducks: {}</p>
    </body>
    </html>
    """.format(len(DUCK_REGISTRY))


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    print("🦆 Starting Duckberry SMS Relay Server...")
    print(f"   Port: {port}")
    print(f"   Heartbeat timeout: {HEARTBEAT_TIMEOUT} minutes")
    print(f"   Duck webhook path: {DUCK_WEBHOOK_PATH}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
