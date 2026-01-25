import os
import requests
from PIL import Image
from io import BytesIO

def download_and_crop_image():
    # URL from the HTML
    url = "https://lh3.googleusercontent.com/aida-public/AB6AXuDtDrOdsWUAnHA6G_XNv0Pg7U5-YdqFwAVytnBqAX1N6LqpDZtGacM2_N2q3D-57LZhpyzNTY9I1NKoz87aXvG6tkdXHrJGZYdSwYeFxzxdZz1D0JRgNzV9M0ir2i6aUZmGeCQGhLrf9eUc451_KRlc-wNL-W_lELRuDKXHZxZ6-xsMt84gVPdgddNMYupGUm8fAZlT4s0iSsGj78ZAmz9f_jx_4kZWuUWcboSJVsbprxNP1gZdCv7Gkr3N6_J29cNmz8ZHJgNdTBo"
    
    # Create directory if not exists
    save_dir = "static/images"
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    save_path = os.path.join(save_dir, "hero_keys.jpg")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        
        # Crop the top 25%
        # (left, upper, right, lower)
        crop_amount = int(height * 0.25)
        box = (0, crop_amount, width, height)
        cropped_img = img.crop(box)
        
        cropped_img.save(save_path)
        print(f"Successfully saved cropped image to {save_path}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    download_and_crop_image()
