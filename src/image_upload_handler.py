"""
Image Upload Handler for Duck Control
Handles web-based image uploads with AI analysis and SMS responses.
"""
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple


def parse_multipart_form_data(body: bytes, content_type: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """
    Parse multipart/form-data manually (Python 3.13 compatible - no cgi module).
    
    Args:
        body: Raw request body
        content_type: Content-Type header value
    
    Returns:
        Tuple of (file_data, filename, user_message)
    """
    try:
        # Extract boundary from Content-Type
        boundary = content_type.split('boundary=')[1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        
        # Split body by boundary
        parts = body.split(('--' + boundary).encode())
        
        file_data = None
        filename = None
        user_message = None
        
        for part in parts:
            if not part or part == b'--\r\n' or part == b'--':
                continue
            
            # Split headers and content
            if b'\r\n\r\n' in part:
                header_section, content = part.split(b'\r\n\r\n', 1)
                header_section = header_section.decode('utf-8', errors='ignore')
                
                # Remove trailing boundary markers
                content = content.rstrip(b'\r\n')
                
                # Check if this is the image field
                if 'name="image"' in header_section:
                    # Extract filename
                    if 'filename="' in header_section:
                        filename_start = header_section.index('filename="') + 10
                        filename_end = header_section.index('"', filename_start)
                        filename = header_section[filename_start:filename_end]
                    file_data = content
                
                # Check if this is the message field
                elif 'name="message"' in header_section:
                    user_message = content.decode('utf-8', errors='ignore').strip()
        
        return file_data, filename, user_message
        
    except Exception as e:
        print(f"⚠️ Multipart parsing error: {e}", flush=True)
        return None, None, None


def handle_image_upload(
    body: bytes,
    content_type: str,
    services
) -> Dict[str, Any]:
    """
    Handle image upload with AI analysis and SMS response.
    
    Args:
        body: Request body with multipart data
        content_type: Content-Type header
        services: ServiceManager instance with all services
    
    Returns:
        Dict with success status, description, ai_response, categories
    
    Raises:
        Exception: On upload/processing errors
    """
    # Parse multipart form data
    file_data, filename, user_message = parse_multipart_form_data(body, content_type)
    
    if not filename or not file_data:
        raise Exception('No image file uploaded')
    
    print(f"📸 Image upload: {filename}", flush=True)
    if user_message:
        print(f"💬 Message: {user_message}", flush=True)
    
    # Save to temp file
    suffix = Path(filename).suffix or '.jpg'
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name
    
    temp_file.write(file_data)
    temp_file.close()
    
    print(f"💾 Saved to: {temp_path}", flush=True)
    
    # Get services from singleton
    vision = services.get_vision_analyzer()
    if not vision:
        raise Exception('Vision system is disabled')
    
    memory_manager = services.get_memory_manager()
    user_manager = services.get_user_manager()
    sms_manager = services.get_sms_manager()
    ai_generator = services.get_ai_response_generator()
    
    # Get current user
    current_user = user_manager.get_current_user()
    sender_name = current_user.get('name', 'Osmund')
    sender_relation = current_user.get('relation', 'owner')
    
    # Get contact for SMS response
    osmund_contact = None
    try:
        contacts = sms_manager.get_all_contacts()
        for contact in contacts:
            if contact['name'] == sender_name:
                osmund_contact = contact
                break
    except Exception as e:
        print(f"⚠️ Could not fetch contact: {e}", flush=True)
    
    # Analyze image
    analysis = vision.analyze_image(
        image_url=temp_path,
        prompt="Beskriv dette bildet på norsk. Vær detaljert og nevn om det er personer, dyr, gjenstander eller steder."
    )
    
    if not analysis:
        raise Exception('Image analysis failed')
    
    description = analysis.get('description', 'Kunne ikke analysere bildet')
    categories = analysis.get('categories', [])
    
    print(f"🖼️  Analysis: {description[:100]}...", flush=True)
    
    # Move image to permanent location
    project_root = Path(__file__).parent.parent
    received_dir = project_root / 'received_images'
    received_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"upload_{sender_name}_{timestamp}{suffix}"
    final_path = received_dir / filename
    
    shutil.move(temp_path, str(final_path))
    print(f"📁 Moved to: {final_path}", flush=True)
    
    # Compress if needed
    vision.compress_image(str(final_path))
    
    # Save to database
    image_id = memory_manager.save_image_memory(
        filepath=str(final_path),
        sender=sender_name,
        description=description,
        categories=categories,
        message_text=user_message or "Uploaded via web interface",
        source_url="local_upload",
        sender_relation=sender_relation
    )
    
    print(f"✅ Saved to database (id={image_id})", flush=True)
    
    # Generate and send AI response via SMS
    ai_response = None
    if osmund_contact and ai_generator:
        try:
            ai_response = ai_generator.generate_image_response(
                image_description=description,
                user_message=user_message,
                sender_name=sender_name,
                model='gpt-4o-mini',
                max_tokens=150
            )
            
            if ai_response:
                print(f"🤖 AI response: {ai_response[:50]}...", flush=True)
                
                sms_result = sms_manager.send_sms(
                    to_number=osmund_contact['phone'],
                    message=ai_response
                )
                
                if sms_result:
                    print(f"📱 SMS sent to {osmund_contact['name']}", flush=True)
                else:
                    print(f"⚠️ SMS sending failed", flush=True)
        except Exception as e:
            print(f"⚠️ AI/SMS response failed: {e}", flush=True)
    
    return {
        'success': True,
        'description': description,
        'categories': categories,
        'image_id': image_id,
        'ai_response': ai_response
    }
