"""
Duck Vision Module
Handles MMS image analysis using GPT-4 Vision.
"""
import os
import requests
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from openai import OpenAI
from PIL import Image
import io


class VisionConfig:
    """Configuration for vision features"""
    ENABLED = True  # Feature flag - set to False to disable
    MODEL = "gpt-4o"  # gpt-4o has vision and is cheaper than gpt-4-turbo
    MAX_TOKENS = 300  # Max tokens for image description
    SAVE_IMAGES = True  # Save images locally
    IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "received_images")
    MAX_IMAGE_SIZE_MB = 5  # Max image size to download
    
    # Image compression settings
    COMPRESS_IMAGES = True  # Compress images to save disk space
    MAX_WIDTH = 1920  # Max width in pixels
    MAX_HEIGHT = 1080  # Max height in pixels
    JPEG_QUALITY = 85  # JPEG quality (1-100, 85 is good balance)
    
    # Auto-cleanup settings
    AUTO_CLEANUP = True  # Delete old images automatically
    MAX_AGE_DAYS = 90  # Delete images older than this (90 days = ~3 months)


class VisionAnalyzer:
    """Analyzes images using GPT-4 Vision"""
    
    def __init__(self, api_key: str):
        """
        Initialize VisionAnalyzer.
        
        Args:
            api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        self.config = VisionConfig()
        
        # Create image directory if it doesn't exist
        if self.config.SAVE_IMAGES and not os.path.exists(self.config.IMAGE_DIR):
            os.makedirs(self.config.IMAGE_DIR, exist_ok=True)
            print(f"✅ Created image directory: {self.config.IMAGE_DIR}", flush=True)
    
    def is_enabled(self) -> bool:
        """Check if vision features are enabled"""
        return self.config.ENABLED
    
    def cleanup_old_images(self) -> int:
        """
        Delete images older than MAX_AGE_DAYS.
        
        Returns:
            Number of images deleted
        """
        if not self.config.AUTO_CLEANUP or not os.path.exists(self.config.IMAGE_DIR):
            return 0
        
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.MAX_AGE_DAYS)
            deleted_count = 0
            
            for filename in os.listdir(self.config.IMAGE_DIR):
                filepath = os.path.join(self.config.IMAGE_DIR, filename)
                
                # Skip if not a file
                if not os.path.isfile(filepath):
                    continue
                
                # Check file age
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if file_time < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"🗑️  Deleted old image: {filename} (age: {(datetime.now() - file_time).days} days)", flush=True)
            
            if deleted_count > 0:
                print(f"✅ Cleanup complete: {deleted_count} old images deleted", flush=True)
            
            return deleted_count
            
        except Exception as e:
            print(f"⚠️ Cleanup failed: {e}", flush=True)
            return 0
    
    def compress_image(self, image_path: str) -> bool:
        """
        Compress and resize image to save disk space.
        
        Args:
            image_path: Path to image file
        
        Returns:
            True if successful, False otherwise
        """
        if not self.config.COMPRESS_IMAGES:
            return True
        
        try:
            # Open image
            img = Image.open(image_path)
            
            # Get original size
            original_size = os.path.getsize(image_path)
            original_width, original_height = img.size
            
            # Calculate new dimensions (maintain aspect ratio)
            max_width = self.config.MAX_WIDTH
            max_height = self.config.MAX_HEIGHT
            
            if original_width > max_width or original_height > max_height:
                # Calculate scaling factor
                width_ratio = max_width / original_width
                height_ratio = max_height / original_height
                scale_factor = min(width_ratio, height_ratio)
                
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                # Resize image
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"📐 Resized: {original_width}x{original_height} → {new_width}x{new_height}", flush=True)
            
            # Convert to RGB if needed (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as JPEG with compression
            output_path = os.path.splitext(image_path)[0] + '.jpg'
            img.save(output_path, 'JPEG', quality=self.config.JPEG_QUALITY, optimize=True)
            
            # If we created a new file (e.g., converted PNG to JPG), remove the original
            if output_path != image_path:
                os.remove(image_path)
            
            new_size = os.path.getsize(output_path)
            compression_ratio = (1 - new_size / original_size) * 100
            
            print(f"🗜️  Compressed: {original_size / 1024:.1f}KB → {new_size / 1024:.1f}KB ({compression_ratio:.1f}% reduction)", flush=True)
            
            return True
            
        except Exception as e:
            print(f"⚠️ Compression failed: {e}", flush=True)
            return False
    
    def download_image(self, image_url: str, sender_name: str = "unknown") -> Optional[str]:
        """
        Download image from URL and save locally.
        
        Args:
            image_url: URL to image (from Twilio MediaUrl)
            sender_name: Name of sender (for filename)
        
        Returns:
            Local filepath if successful, None otherwise
        """
        if not self.config.SAVE_IMAGES:
            return None
        
        try:
            # Download image
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Check size
            size_mb = len(response.content) / (1024 * 1024)
            if size_mb > self.config.MAX_IMAGE_SIZE_MB:
                print(f"⚠️ Image too large: {size_mb:.2f}MB (max {self.config.MAX_IMAGE_SIZE_MB}MB)", flush=True)
                return None
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Get file extension from Content-Type or URL
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'gif' in content_type:
                ext = 'gif'
            else:
                ext = 'jpg'  # default
            
            filename = f"{timestamp}_{sender_name}.{ext}"
            filepath = os.path.join(self.config.IMAGE_DIR, filename)
            
            # Save image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            print(f"✅ Image saved: {filepath} ({size_mb:.2f}MB)", flush=True)
            
            # Compress image
            self.compress_image(filepath)
            
            # Check if filename changed after compression (e.g., .png → .jpg)
            jpg_path = os.path.splitext(filepath)[0] + '.jpg'
            if os.path.exists(jpg_path) and jpg_path != filepath:
                filepath = jpg_path
            
            return filepath
            
        except Exception as e:
            print(f"⚠️ Failed to download image: {e}", flush=True)
            return None
    
    def analyze_image(self, image_url: str, prompt: str = None) -> Optional[Dict[str, Any]]:
        """
        Analyze image using GPT-4 Vision.
        
        Args:
            image_url: URL to image or local filepath
            prompt: Optional custom prompt (defaults to general description)
        
        Returns:
            Dict with 'description', 'categories', 'confidence' or None if failed
        """
        if not self.is_enabled():
            print("⚠️ Vision features are disabled", flush=True)
            return None
        
        try:
            # Default prompt if none provided
            if prompt is None:
                prompt = """Beskriv dette bildet i detalj på norsk. Inkluder:
- Hva er hovedmotivet?
- Hvilke objekter/personer/dyr ser du?
- Farger, setting, stemning
- Andre viktige detaljer

Svar på norsk i 2-3 setninger."""
            
            # Check if it's a local file or URL
            if os.path.exists(image_url):
                # Local file - encode to base64
                with open(image_url, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Determine image type
                ext = os.path.splitext(image_url)[1].lower()
                if ext == '.png':
                    media_type = 'image/png'
                elif ext == '.gif':
                    media_type = 'image/gif'
                else:
                    media_type = 'image/jpeg'
                
                image_content = {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{image_data}"
                    }
                }
            else:
                # Remote URL
                image_content = {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            
            # Call GPT-4 Vision
            response = self.client.chat.completions.create(
                model=self.config.MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            image_content
                        ]
                    }
                ],
                max_tokens=self.config.MAX_TOKENS
            )
            
            description = response.choices[0].message.content
            
            # Simple category detection based on keywords
            categories = []
            desc_lower = description.lower()
            
            category_keywords = {
                'mat': ['mat', 'måltid', 'pizza', 'burger', 'dessert', 'frukt', 'grønnsak'],
                'dyr': ['hund', 'katt', 'fugl', 'dyr', 'and', 'kylling'],
                'bil': ['bil', 'tesla', 'bmw', 'mercedes', 'kjøretøy', 'auto'],
                'mennesker': ['person', 'menneske', 'mann', 'kvinne', 'barn', 'ansikt'],
                'natur': ['skog', 'fjell', 'hav', 'strand', 'tre', 'blomst', 'landskap'],
                'teknologi': ['telefon', 'pc', 'skjerm', 'laptop', 'elektronikk'],
                'hus': ['hus', 'bygning', 'rom', 'kjøkken', 'stue', 'soverom']
            }
            
            for category, keywords in category_keywords.items():
                if any(keyword in desc_lower for keyword in keywords):
                    categories.append(category)
            
            if not categories:
                categories = ['annet']
            
            result = {
                'description': description,
                'categories': categories,
                'model': self.config.MODEL,
                'timestamp': datetime.now().isoformat()
            }
            
            print(f"✅ Image analyzed: {description[:100]}...", flush=True)
            print(f"   Categories: {', '.join(categories)}", flush=True)
            
            return result
            
        except Exception as e:
            print(f"⚠️ Image analysis failed: {e}", flush=True)
            return None
    
    def process_mms(self, image_url: str, sender_name: str, message_text: str = "", 
                    memory_manager = None, sender_relation: str = "") -> Optional[Dict[str, Any]]:
        """
        Complete MMS processing pipeline.
        
        Args:
            image_url: URL to image from Twilio
            sender_name: Name of sender
            message_text: Optional text message accompanying the image
            memory_manager: MemoryManager instance for saving to database
            sender_relation: Relation to sender (owner, family, friend)
        
        Returns:
            Dict with 'description', 'local_path', 'categories' or None if failed
        """
        if not self.is_enabled():
            return None
        
        print(f"📸 Processing MMS from {sender_name}", flush=True)
        
        # Run cleanup before processing (delete old images)
        self.cleanup_old_images()
        
        # Step 1: Download image
        local_path = self.download_image(image_url, sender_name)
        
        # Step 2: Analyze image (use URL if download failed)
        analysis_source = local_path if local_path else image_url
        
        # Custom prompt if there's accompanying text
        if message_text:
            prompt = f"""Beskriv dette bildet i detalj på norsk. 
Avsenderen skrev: "{message_text}"

Inkluder:
- Hva er hovedmotivet?
- Hvordan relaterer bildet til meldingen?
- Er det mennesker på bildet? Hvor mange? Beskriv dem (alder, kjønn, utseende)
- Viktige detaljer

Svar på norsk i 2-4 setninger."""
        else:
            prompt = """Beskriv dette bildet i detalj på norsk. Inkluder:
- Hva er hovedmotivet?
- Er det mennesker på bildet? Hvor mange? Beskriv dem (alder, kjønn, utseende)
- Hvilke objekter/personer/dyr ser du?
- Farger, setting, stemning
- Andre viktige detaljer

Svar på norsk i 2-4 setninger."""
        
        analysis = self.analyze_image(analysis_source, prompt)
        
        if analysis:
            analysis['local_path'] = local_path
            analysis['sender'] = sender_name
            analysis['message_text'] = message_text
            analysis['source_url'] = image_url
            analysis['sender_relation'] = sender_relation
            
            # Save to database if memory_manager provided
            if memory_manager and local_path:
                try:
                    image_id = memory_manager.save_image_memory(
                        filepath=local_path,
                        sender=sender_name,
                        description=analysis['description'],
                        categories=analysis['categories'],
                        message_text=message_text,
                        source_url=image_url,
                        sender_relation=sender_relation
                    )
                    analysis['image_id'] = image_id
                    print(f"✅ Saved to image_history (id={image_id})", flush=True)
                except Exception as e:
                    print(f"⚠️ Failed to save to database: {e}", flush=True)
        
        return analysis


def test_vision():
    """Test function for vision module"""
    import sys
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ OPENAI_API_KEY not found in .env")
        sys.exit(1)
    
    analyzer = VisionAnalyzer(api_key)
    
    # Test with a sample image URL
    test_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1200px-Cat03.jpg"
    
    print(f"Testing with image: {test_url}")
    result = analyzer.process_mms(test_url, "TestUser", "Se på denne katten!")
    
    if result:
        print(f"\n✅ Test successful!")
        print(f"Description: {result['description']}")
        print(f"Categories: {', '.join(result['categories'])}")
        print(f"Local path: {result.get('local_path', 'Not saved')}")
    else:
        print("\n❌ Test failed")


if __name__ == "__main__":
    test_vision()
