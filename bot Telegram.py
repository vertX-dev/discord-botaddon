import requests
import io
from PIL import Image
import time
import json
import zipfile
from datetime import datetime

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        
    def get_updates(self, offset=None):
        """Get updates from Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": 30}
        if offset:
            params["offset"] = offset
        
        try:
            response = requests.get(url, params=params)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting updates: {e}")
            return {"ok": False, "result": []}
    
    def send_message(self, chat_id, text):
        """Send a text message"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text
        }
        
        try:
            response = requests.post(url, data=data)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending message: {e}")
            return {"ok": False}
    
    def send_document(self, chat_id, document_data, filename, caption=None, mime_type=None):
        """Send a document"""
        url = f"{self.base_url}/sendDocument"
        
        # Determine MIME type based on file extension if not provided
        if mime_type is None:
            if filename.lower().endswith('.zip'):
                mime_type = "application/zip"
            else:
                mime_type = "image/png"
        
        files = {"document": (filename, document_data, mime_type)}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        
        try:
            response = requests.post(url, files=files, data=data)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending document: {e}")
            return {"ok": False}
    
    def get_file(self, file_id):
        """Get file info"""
        url = f"{self.base_url}/getFile"
        params = {"file_id": file_id}
        
        try:
            response = requests.get(url, params=params)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting file info: {e}")
            return {"ok": False}
    
    def download_file(self, file_path):
        """Download file from Telegram servers"""
        url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        
        try:
            response = requests.get(url)
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return None

def compress_image(image, max_size=(64, 64)):
    """Compress image to fit within max_size while maintaining aspect ratio"""
    original_size = image.size
    
    # If image is already within limits, return as is
    if original_size[0] <= max_size[0] and original_size[1] <= max_size[1]:
        return image
    
    # Calculate the scaling factor to fit within max_size
    scale_x = max_size[0] / original_size[0]
    scale_y = max_size[1] / original_size[1]
    scale = min(scale_x, scale_y)
    
    # Calculate new dimensions
    new_width = int(original_size[0] * scale)
    new_height = int(original_size[1] * scale)
    
    # Resize the image using high-quality resampling
    compressed_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    print(f"Compressed image from {original_size} to {compressed_image.size}")
    return compressed_image

def apply_column_saturation(image, num_columns, saturation_percent=100):
    """Apply specified % black saturation to the first num_columns columns"""
    # Create a copy of the image
    result_image = image.copy()
    
    # Convert to RGBA if not already
    if result_image.mode != 'RGBA':
        result_image = result_image.convert('RGBA')
    
    # Get image dimensions
    width, height = result_image.size
    
    # Clamp num_columns to valid range
    num_columns = min(num_columns, width)
    
    # Calculate saturation factor (0.0 to 1.0)
    saturation_factor = saturation_percent / 100.0
    
    # Process each pixel in the image
    pixels = result_image.load()
    
    for y in range(height):
        for x in range(num_columns):  # Only process first num_columns columns
            r, g, b, a = pixels[x, y]
            
            # Only process non-transparent pixels
            if a > 0:
                # Apply saturation: interpolate between original color and black
                new_r = int(r * (1 - saturation_factor))
                new_g = int(g * (1 - saturation_factor))
                new_b = int(b * (1 - saturation_factor))
                
                pixels[x, y] = (new_r, new_g, new_b, a)
    
    return result_image

def process_image_columns(image, saturation_percent=100):
    """Process image and create column-wise saturated versions"""
    # Convert to RGBA if needed
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Get image dimensions
    width, height = image.size
    
    # Create list to store processed images
    processed_images = []
    
    # Process each column step (0 to width)
    for col in range(width + 1):  # +1 to include final state with all columns saturated
        # Apply saturation to first 'col' columns
        processed_img = apply_column_saturation(image, col, saturation_percent)
        processed_images.append(processed_img)
    
    return processed_images

def parse_saturation_command(text):
    """Parse saturation percentage from user message"""
    # Look for patterns like "50%", "75 %", "percent 30", etc.
    import re
    
    # Try to find percentage patterns
    patterns = [
        r'(\d+)%',  # "50%"
        r'(\d+)\s*%',  # "50 %"
        r'percent\s*(\d+)',  # "percent 50"
        r'(\d+)\s*percent',  # "50 percent"
        r'saturation\s*(\d+)',  # "saturation 50"
        r'(\d+)\s*saturation',  # "50 saturation"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                value = int(match.group(1))
                # Clamp value between 1 and 100
                return max(1, min(100, value))
            except ValueError:
                continue
    
    return 100  # Default to 100% if no valid percentage found

def image_to_bytes(image, optimize=True):
    """Convert PIL Image to bytes with optional optimization"""
    img_byte_arr = io.BytesIO()
    
    # Save with optimization to reduce file size
    save_params = {'format': 'PNG'}
    if optimize:
        save_params['optimize'] = True
        save_params['compress_level'] = 6  # Good balance between compression and speed
    
    image.save(img_byte_arr, **save_params)
    return img_byte_arr.getvalue()

def create_zip_archive(processed_images, original_filename, compressed_size, saturation_percent):
    """Create a ZIP archive containing all processed images"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
        # Add each processed image to the ZIP
        for i, processed_img in enumerate(processed_images):
            img_bytes = image_to_bytes(processed_img)
            
            # Create filename for this image
            filename = f"columns_{i:02d}_of_{len(processed_images)-1:02d}_{saturation_percent}pct.png"
            
            # Add image to ZIP
            zip_file.writestr(filename, img_bytes)
        
        # Create a readme file with information
        readme_content = f"""Column Saturation Images
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Original file: {original_filename}
Processed size: {compressed_size[0]}x{compressed_size[1]}
Saturation level: {saturation_percent}%
Total images: {len(processed_images)}

File descriptions:
- columns_00_of_XX_{saturation_percent}pct.png: Original image (0 columns affected)
- columns_01_of_XX_{saturation_percent}pct.png: Column 1 with {saturation_percent}% saturation
- columns_02_of_XX_{saturation_percent}pct.png: Columns 1-2 with {saturation_percent}% saturation
- ...
- columns_XX_of_XX_{saturation_percent}pct.png: All columns with {saturation_percent}% saturation

Each image shows {saturation_percent}% saturation applied to columns from left to right.
Only non-transparent pixels are affected.
"""
        zip_file.writestr("README.txt", readme_content)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
    """Convert PIL Image to bytes with optional optimization"""
    img_byte_arr = io.BytesIO()
    
    # Save with optimization to reduce file size
    save_params = {'format': 'PNG'}
    if optimize:
        save_params['optimize'] = True
        save_params['compress_level'] = 6  # Good balance between compression and speed
    
    image.save(img_byte_arr, **save_params)
    return img_byte_arr.getvalue()

def main():
    # Replace with your bot token
    BOT_TOKEN = ""
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Please replace BOT_TOKEN with your actual bot token")
        return
    
    bot = TelegramBot(BOT_TOKEN)
    
    print("Bot started. Waiting for messages...")
    
    last_update_id = None
    user_saturation = {}  # Store saturation settings per user
    
    while True:
        try:
            # Get updates
            updates = bot.get_updates(offset=last_update_id)
            
            if not updates.get("ok", False):
                time.sleep(1)
                continue
            
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1
                
                # Skip if no message
                if "message" not in update:
                    continue
                
                message = update["message"]
                chat_id = message["chat"]["id"]
                
                # Handle text messages
                if "text" in message:
                    text = message["text"]
                    
                    if text.lower() in ["/start", "/help"]:
                        help_text = (
                            "Welcome to the Enhanced Column Saturation Bot!\n\n"
                            "📋 Instructions:\n"
                            "1. Send me a PNG image as a DOCUMENT (not as photo!)\n"
                            "2. Images larger than 64x64 will be automatically compressed\n"
                            "3. I'll return a ZIP archive with all processed images\n\n"
                            "🎛️ Saturation Control:\n"
                            "• Default: 100% saturation (fully black)\n"
                            "• Custom: Send message with percentage before image\n"
                            "• Examples: '50%', '75 percent', 'saturation 30'\n"
                            "• Valid range: 1% to 100%\n\n"
                            "🔄 How it works:\n"
                            "Each image shows specified % saturation applied to columns:\n"
                            "• Image 1 = 0 columns affected (original)\n"
                            "• Image 2 = 1 column with X% saturation\n"
                            "• Image 3 = 2 columns with X% saturation\n"
                            "• ... and so on until all columns are saturated\n"
                            "• Only non-transparent pixels are affected\n\n"
                            "🗜️ Features:\n"
                            "• Automatic image compression for large images\n"
                            "• Aspect ratio is maintained\n"
                            "• High-quality resampling is used\n"
                            "• All images delivered in a single ZIP file\n"
                            "• Includes README.txt with file descriptions\n\n"
                            "⚠️ IMPORTANT: Send PNG as DOCUMENT, not as photo!\n"
                            "Photos are converted to JPEG and lose transparency."
                        )
                        bot.send_message(chat_id, help_text)
                    else:
                        # Check if message contains saturation percentage
                        saturation_percent = parse_saturation_command(text)
                        if saturation_percent != 100:  # User specified a custom percentage
                            user_saturation[chat_id] = saturation_percent
                            bot.send_message(chat_id, 
                                f"✅ Saturation level set to {saturation_percent}%\n"
                                f"Now send me a PNG image as a document to process!")
                        else:
                            # Reset to default if no valid percentage found
                            user_saturation[chat_id] = 100
                            bot.send_message(chat_id, 
                                f"📝 Current saturation: {user_saturation.get(chat_id, 100)}%\n"
                                f"Send a percentage (e.g., '50%') to change, or send a PNG image to process.\n"
                                f"Use /help for detailed instructions.")
                
                # Handle document messages (for PNG files)
                elif "document" in message:
                    try:
                        document = message["document"]
                        file_name = document.get("file_name", "")
                        file_size = document.get("file_size", 0)
                        mime_type = document.get("mime_type", "")
                        
                        # Check if it's a PNG file
                        if not (file_name.lower().endswith('.png') or mime_type == 'image/png'):
                            bot.send_message(chat_id, "Error: Please send a PNG image as a document (not as a photo)")
                            continue
                        
                        # Check file size (optional, but good practice)
                        if file_size > 5 * 1024 * 1024:  # 5MB limit
                            bot.send_message(chat_id, "Error: File too large. Maximum size is 5MB.")
                            continue
                        
                        file_id = document["file_id"]
                        
                        # Get file info
                        file_info = bot.get_file(file_id)
                        if not file_info.get("ok", False):
                            bot.send_message(chat_id, "Error: Could not get file information")
                            continue
                        
                        file_path = file_info["result"]["file_path"]
                        
                        # Download the file
                        file_data = bot.download_file(file_path)
                        if not file_data:
                            bot.send_message(chat_id, "Error: Could not download file")
                            continue
                        
                        # Open image with PIL
                        image = Image.open(io.BytesIO(file_data))
                        original_size = image.size
                        
                        # Compress image if needed
                        image = compress_image(image)
                        compressed_size = image.size
                        
                        # Get user's saturation setting (default to 100%)
                        saturation_percent = user_saturation.get(chat_id, 100)
                        
                        # Notify user about compression if it occurred
                        if original_size != compressed_size:
                            bot.send_message(chat_id, 
                                f"🗜️ Image compressed from {original_size[0]}x{original_size[1]} to {compressed_size[0]}x{compressed_size[1]}")
                        
                        bot.send_message(chat_id, 
                            f"Processing {compressed_size[0]}x{compressed_size[1]} image with {saturation_percent}% saturation.\n"
                            f"Creating {compressed_size[0] + 1} variations and compressing to ZIP...")
                        
                        # Process the image with user's saturation setting
                        processed_images = process_image_columns(image, saturation_percent)
                        
                        # Create ZIP archive with all processed images
                        zip_data = create_zip_archive(processed_images, file_name, compressed_size, saturation_percent)
                        
                        # Create ZIP filename
                        base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                        zip_filename = f"{base_name}_column_saturation_{saturation_percent}pct_{compressed_size[0]}x{compressed_size[1]}.zip"
                        
                        # Create caption for the ZIP file
                        zip_caption = (
                            f"📁 Column Saturation Archive\n"
                            f"🖼️ {len(processed_images)} PNG images\n"
                            f"📏 {compressed_size[0]}x{compressed_size[1]} pixels\n"
                            f"🎛️ {saturation_percent}% saturation level\n"
                            f"📄 Includes README.txt with descriptions"
                        )
                        
                        # Send the ZIP file
                        result = bot.send_document(chat_id, zip_data, zip_filename, zip_caption, "application/zip")
                        
                        if result.get("ok", False):
                            bot.send_message(chat_id, 
                                f"✅ Success! ZIP archive contains {len(processed_images)} processed images.\n"
                                f"📦 File size: {len(zip_data)} bytes\n"
                                f"🎛️ Saturation level: {saturation_percent}%\n"
                                f"💡 Extract the ZIP to access all images and the README file.\n\n"
                                f"💬 Send a new percentage (e.g., '75%') to change saturation level.")
                        else:
                            bot.send_message(chat_id, "❌ Failed to send ZIP archive. Please try again.")
                            print(f"Failed to send ZIP file: {result}")
                        
                    except ValueError as e:
                        bot.send_message(chat_id, f"Error: {str(e)}")
                    except Exception as e:
                        print(f"Error processing image: {e}")
                        bot.send_message(chat_id, "Error: Failed to process image. Please make sure it's a valid PNG file.")
                
                # Handle photo messages (inform user about document upload)
                elif "photo" in message:
                    bot.send_message(chat_id, 
                        "⚠️ Photos are automatically converted to JPEG by Telegram, which removes transparency.\n\n"
                        "Please send your PNG image as a DOCUMENT instead:\n"
                        "1. Click the 📎 attachment button\n"
                        "2. Select 'Document' (not 'Photo')\n"
                        "3. Choose your PNG file\n\n"
                        "This preserves the PNG format and transparency information."
                    )
                
                # Handle unsupported message types
                else:
                    bot.send_message(chat_id, 
                        "Please send a PNG image as a DOCUMENT or use /help for instructions.\n\n"
                        "⚠️ Don't send as photo - use the document attachment option to preserve PNG format!"
                    )
        
        except KeyboardInterrupt:
            print("\nBot stopped by user")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()