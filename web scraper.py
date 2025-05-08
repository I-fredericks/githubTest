import requests
from bs4 import BeautifulSoup  # For parsing and navigating HTML/XML content
import customtkinter as ctk
from tkinter import messagebox, filedialog  
from PIL import Image 
import io  # handling byte streams
from urllib.parse import urljoin
import threading  # Enables concurrent execution of code (used to keep the GUI responsive)
import os 
from pytube import YouTube
import socket  
from selenium import webdriver 
from selenium.webdriver.chrome.options import Options
import time
import random
from time import sleep
from random import uniform 
import hashlib 
from datetime import datetime


# Sites that can be scraped
# https://scholar.google.com/
# https://doaj.org/
# https://www.amazon.com/
# http://annascloset.kesug.com/?i=1
# http://varifiedfoodandbakery.kesug.com/?i=1
# https://www.youtube.com/watch?v=GQbrVAyoQD8
# https://vimeo.com/

# Global variables
image_urls = []
video_urls = []
pdf_urls = []
current_image_index = 0
use_selenium = False

# List of user agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
]

def init_selenium():
    """Initialize and return a headless Chrome WebDriver with anti-detection settings"""
    options = Options()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    return webdriver.Chrome(options=options)

def extract_videos(soup, base_url):
    """Extract video URLs from the webpage"""
    videos = []
    for video in soup.find_all('video'):
        if video.get('src'):
            videos.append(urljoin(base_url, video['src']))
        elif video.find('source') and video.find('source').get('src'):
            videos.append(urljoin(base_url, video.find('source')['src']))
    
    # Improved iframe handling for embedded videos
    for iframe in soup.find_all('iframe'):
        if iframe.get('src'):
            src = iframe['src']
            if any(domain in src for domain in ['youtube.com','vimeo.com']):
                videos.append(src)
                # Extract YouTube video ID if present
                if 'youtube.com' in src or 'youtu.be' in src:
                    video_id = None
                    if 'youtube.com/embed/' in src:
                        video_id = src.split('youtube.com/embed/')[1].split('?')[0]
                    elif 'youtu.be/' in src:
                        video_id = src.split('youtu.be/')[1].split('?')[0]
                    elif 'youtube.com/watch?v=' in src:
                        video_id = src.split('v=')[1].split('&')[0]
                    
                    if video_id:
                        videos.append(f"https://www.youtube.com/watch?v={video_id}")
    
    return list(set(videos))  # Remove duplicates

def start_loading():
    """Show loading state in UI"""
    loading_label.configure(text="Scraping... Please wait ⏳")
    scrape_button.configure(state="disabled")
    selenium_toggle.configure(state="disabled")

def stop_loading():
    """Hide loading state in UI"""
    loading_label.configure(text="")
    scrape_button.configure(state="normal")
    selenium_toggle.configure(state="normal")

def download_youtube_video(url, download_dir):
    try:
        from pytube import YouTube
        
        # Create YouTube object
        yt = YouTube(url)
        
        # Get the highest resolution stream
        stream = yt.streams.get_highest_resolution()
        
        # Sanitize the filename
        filename = f"{yt.title}.mp4"
        filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_', ' ')).strip()
        
        # Download the video
        output_path = stream.download(output_path=download_dir, filename=filename)
        
        # Verify download
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True
        return False
        
    except Exception as e:
        print(f"Failed to download YouTube video {url}: {str(e)}")
        return False

def download_files():
    """Thread function for downloading files"""
    button = video_download_button  # Assuming this is for video downloads
    button.configure(state="disabled", text="Downloading...")
    success_count = 0
    
    # Ensure download directory exists
    try:
        os.makedirs(download_dir, exist_ok=True)
    except Exception as e:
        messagebox.showerror("Error", f"Cannot create download directory: {str(e)}")
        button.configure(state="normal", text=f"Download VIDEOS ({len(urls)})")
        return
    
    for i, media_url in enumerate(urls):
        try:
            # Handle YouTube videos
            if any(domain in media_url for domain in ['youtube.com', 'youtu.be']):
                if download_youtube_video(media_url, download_dir):
                    success_count += 1
                continue
            
            # [Rest of your existing download code for non-YouTube videos]
            
        except Exception as e:
            print(f"Failed to download {media_url}: {str(e)}")
    
    button.configure(state="normal", text=f"Download VIDEOS ({len(urls)})")
    message = f"Successfully downloaded {success_count} out of {len(urls)} VIDEOS"
    embedded_count = sum(1 for url in urls if any(domain in url for domain in ['youtube.com', 'youtu.be', 'vimeo.com']))
    if embedded_count > 0:
        message += f"\nNote: {embedded_count} embedded videos detected (YouTube/Vimeo).\n"
        message += "YouTube videos are downloaded using pytube.\n"
        message += "Vimeo videos currently require manual download."
    messagebox.showinfo("Download Complete", message)

def download_media(media_type):
    """Download all media files of specified type (pdf or video)"""
    urls = pdf_urls if media_type == "pdf" else video_urls
    if not urls:
        messagebox.showinfo("Info", f"No {media_type.upper()}s found to download")
        return
    
    download_dir = filedialog.askdirectory(title=f"Select Download Directory for {media_type.upper()}s")
    if not download_dir:
        return
    
    try:
        os.makedirs(download_dir, exist_ok=True)
        
        def download_files():
            """Thread function for downloading files"""
            button = pdf_download_button if media_type == "pdf" else video_download_button
            button.configure(state="disabled", text="Downloading...")
            success_count = 0
            
            # Ensure download directory exists
            try:
                os.makedirs(download_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create download directory: {str(e)}")
                button.configure(state="normal", text=f"Download {media_type.upper()}s ({len(urls)})")
                return
            
            for i, media_url in enumerate(urls):
                try:
                    # Handle YouTube/Vimeo videos specially
                    if media_type == "video":
                        if any(domain in media_url for domain in ['youtube.com', 'youtu.be']):
                            if download_youtube_video(media_url, download_dir):
                                success_count += 1
                            continue
                        elif 'vimeo.com' in media_url:
                            # Vimeo requires different handling (could implement later)
                            continue
                    
                    # Regular file download
                    headers = {"User-Agent": random.choice(USER_AGENTS)}
                    response = requests.get(media_url, headers=headers, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    # Improved filename handling
                    filename = os.path.basename(media_url.split('?')[0])
                    if not filename.strip():
                        filename = f"{media_type}_{i+1}"
                        
                    # Add appropriate extension if missing
                    if media_type == "pdf" and not filename.lower().endswith('.pdf'):
                        filename += ".pdf"
                    elif media_type == "video" and not any(filename.lower().endswith(ext) for ext in ['.mp4', '.webm', '.ogg', '.mov']):
                        filename += ".mp4"
                    
                    # Sanitize filename
                    filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_', ' ')).strip()
                    if not filename:
                        filename = f"{media_type}_{1+1}"
                        
                    filepath = os.path.join(download_dir, filename)
                    
                    # Download with progress (for large files)
                    with open(filepath, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                            f.flush() # Ensure all data is writing to disk
                    # Verify file was saved
                    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                        success_count += 1
                    else:
                        raise IOError("File was not saved properly")
                except IOError as e:
                    print(f"Failed to save file {filename}: {str(e)}")
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except:
                            pass
                        continue
                    
                    # Add random delay between downloads to be polite
                    sleep(uniform(0.5, 2.5))
                except Exception as e:
                    print(f"Failed to download {media_url}: {str(e)}")
            
            button.configure(state="normal", text=f"Download {media_type.upper()}s ({len(urls)})")
            message = f"Successfully downloaded {success_count} out of {len(urls)} {media_type.upper()}s"
            if media_type == "video":
                embedded_count = sum(1 for url in urls if any(domain in url for domain in ['youtube.com', 'youtu.be', 'vimeo.com']))
                if embedded_count > 0:
                    message += f"\nNote: {embedded_count} embedded videos detected (YouTube/Vimeo).\n"
                    message += "YouTube videos are downloaded using pytube.\n"
                    message += "Vimeo videos currently require manual download."
            messagebox.showinfo("Download Complete", message)
        
        threading.Thread(target=download_files, daemon=True).start()
        
    except Exception as e:
        button = pdf_download_button if media_type == "pdf" else video_download_button
        button.configure(state="normal", text=f"Download {media_type.upper()}s ({len(urls)})")
        messagebox.showerror("Error", f"Failed to download {media_type.upper()}s: {str(e)}")

def scrape_with_retry(url, headers, max_retries=3):
    """Attempt to scrape a URL with retries and delays"""
    session = requests.Session()
    
    for attempt in range(max_retries):
        try:
            # Rotate user agent for each attempt
            headers["User-Agent"] = random.choice(USER_AGENTS)
            
            # First request to get cookies
            if attempt == 0:
                session.get(url, headers=headers, timeout=10)
                sleep(uniform(1, 3))  # Initial delay
            
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                if attempt < max_retries - 1:
                    delay = uniform(2, 5)  # Random delay between 2-5 seconds
                    sleep(delay)
                    continue
            raise
    return None

def toggle_selenium():
    """Toggle between using requests and selenium"""
    global use_selenium
    use_selenium = not use_selenium
    selenium_toggle.configure(text=f"Use Selenium: {'ON' if use_selenium else 'OFF'}")

def generate_signature():
    """Generate a proper signature for the results"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signature = hashlib.sha256(timestamp.encode()).hexdigest()[:16]  # Shortened for display
    return f"Signed by: Mr Frederick\nTimestamp: {timestamp}\nSignature: {signature}"

def scrape_website():
    """Main function to scrape website content"""
    global image_urls, video_urls, pdf_urls, current_image_index
    url = url_entry.get().strip()
    
    if not url:
        messagebox.showerror("Error", "Please enter a URL")
        return
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url  # Auto-prepend https:// if missing
    
    start_loading()

    def fetch_data():
        try:
            # Check DNS resolution first
            try:
                domain = url.split('/')[2]
                socket.gethostbyname(domain)
            except socket.gaierror:
                stop_loading()
                messagebox.showerror("DNS Error", "Failed to resolve domain name. Check your internet connection.")
                return

            if use_selenium:
                try:
                    driver = init_selenium()
                    driver.get(url)
                    time.sleep(3)  # Allow page to load
                    soup = BeautifulSoup(driver.page_source, "html.parser")
                    driver.quit()
                except Exception as e:
                    stop_loading()
                    messagebox.showerror("Selenium Error", f"Failed to use Selenium:\n{str(e)}")
                    return
            else:
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Cache-Control": "max-age=0"
                }
                
                response = scrape_with_retry(url, headers)
                if response is None:
                    stop_loading()
                    messagebox.showerror("Error", "Failed to access website after multiple attempts")
                    return
                
                soup = BeautifulSoup(response.text, "html.parser")

            # Extract content
            page_title = soup.title.string.strip() if soup.title else "No Title Found"
            meta_description = soup.find("meta", attrs={"name": "description"})
            meta_content = meta_description["content"].strip() if meta_description else "No Description Available"
            
            # Improved heading extraction
            headings = []
            for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                for i, h in enumerate(soup.find_all(tag)):
                    headings.append(f"{tag.upper()} #{i+1}: {h.text.strip()}")
            
            links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]

            global image_urls, video_urls, pdf_urls
            # Improved image URL extraction
            image_urls = []
            for img in soup.find_all("img", src=True):
                src = img["src"].strip()
                if src and not src.startswith("data:image"):  # Skip embedded images
                    image_urls.append(urljoin(url, src))
            
            video_urls = list(set(extract_videos(soup, url)))
            pdf_urls = list(set(urljoin(url, a["href"]) for a in soup.find_all("a", href=True) 
                        if a["href"].lower().endswith(".pdf") and not a["href"].startswith("#")))

            stop_loading()
            current_image_index = 0
            display_results(page_title, meta_content, headings, links)
            
            if image_urls:
                display_image(0)
            else:
                img_label.configure(image="", text="No image found")
            
            pdf_download_button.configure(
                text=f"Download PDFs ({len(pdf_urls)})", 
                state="normal" if pdf_urls else "disabled"
            )
            video_download_button.configure(
                text=f"Download Videos ({len(video_urls)})", 
                state="normal" if video_urls else "disabled"
            )

        except requests.exceptions.RequestException as e:
            stop_loading()
            messagebox.showerror("Connection Error", f"Failed to connect to website:\n{str(e)}")
        except Exception as e:
            stop_loading()
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

    threading.Thread(target=fetch_data, daemon=True).start()

def display_results(title, description, headings, links):
    """Display scraped results in the text widget"""
    result_text.configure(state="normal")
    result_text.delete("1.0", "end")
    result_text.insert("end", f"** Page Title **\n{title}\n\n")
    result_text.insert("end", f"** Meta Description **\n{description}\n\n")
    
    sections = [
        ("Headings", headings),
        ("Links", links[:50]),  # Limit to first 50 links to avoid overload
        ("Images Found", [str(len(image_urls))]),
        ("Videos Found", [str(len(video_urls))]),
        ("PDFs Found", [str(len(pdf_urls))])
    ]
    
    for section_name, content in sections:
        if content:
            result_text.insert("end", f"** {section_name} **\n" + "\n".join(content) + "\n\n")

    # Add signature at the bottom
    result_text.insert("end", "---\n")
    result_text.insert("end", generate_signature() + "\n")
    
    if not any(content for _, content in sections):
        result_text.insert("end", "No relevant data found on the page.")

    result_text.configure(state="disabled")

def display_image(index):
    """Display image at specified index"""
    global current_image_index
    if not image_urls:
        img_label.configure(image=None, text="No images available")
        return
    
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = requests.get(image_urls[index], headers=headers, stream=True, timeout=10)
        response.raise_for_status()
        
        # Load image with error handling
        try:
            img = Image.open(io.BytesIO(response.content))
            img.thumbnail((300, 300), Image.LANCZOS)
            ctk_img = ctk.CTkImage(dark_image=img, size=(img.width, img.height))
            img_label.configure(image=ctk_img, text="")
            img_label.image = ctk_img
            current_image_index = index
            small_next_button.configure(state="normal" if current_image_index < len(image_urls) - 1 else "disabled")
        except Exception as img_error:
            img_label.configure(image=None, text=f"Image format not supported\n{str(img_error)}")
            
    except Exception as e:
        img_label.configure(image=None, text="Failed to load image")

def next_image(): 
    """Display next image"""
    if image_urls and current_image_index < len(image_urls) - 1:
        display_image(current_image_index + 1)

def prev_image(): 
    """Display previous image"""
    if image_urls and current_image_index > 0:
        display_image(current_image_index - 1)

def save_results():
    """Save scraped results to a file"""
    text = result_text.get("1.0", "end").strip()
    if not text:
        messagebox.showerror("Error", "No data to save.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt", 
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(text)
            messagebox.showinfo("Success", "Results saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")

# GUI Setup
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Web Scraper Developed by Mr Frederick")
root.geometry("900x700")  # Slightly larger window
root.minsize(800, 600)  # Set minimum window size

# URL Input Frame
url_frame = ctk.CTkFrame(root)
url_frame.pack(pady=10, padx=10, fill="x")

url_label = ctk.CTkLabel(url_frame, text="Enter Website URL:")
url_label.pack(side="left", padx=5)

url_entry = ctk.CTkEntry(url_frame, width=500, placeholder_text="https://example.com")
url_entry.pack(side="left", padx=5, expand=True, fill="x")

selenium_toggle = ctk.CTkButton(
    url_frame, 
    text=f"Use Selenium: {'ON' if use_selenium else 'OFF'}", 
    command=toggle_selenium,
    width=120
)
selenium_toggle.pack(side="right", padx=5)

# Loading Label
loading_label = ctk.CTkLabel(root, text="", font=("Arial", 12))
loading_label.pack(pady=5)

# Buttons
button_frame = ctk.CTkFrame(root)
button_frame.pack(pady=10, padx=10, fill="x")

scrape_button = ctk.CTkButton(button_frame, text="Scrape", command=scrape_website)
scrape_button.pack(side="left", padx=5)
save_button = ctk.CTkButton(button_frame, text="Save Results", command=save_results)
save_button.pack(side="left", padx=5)
video_download_button = ctk.CTkButton(
    button_frame, 
    text="Download Videos (0)", 
    command=lambda: download_media("video"), 
    state="disabled"
)
video_download_button.pack(side="left", padx=5)
pdf_download_button = ctk.CTkButton(
    button_frame, 
    text="Download PDFs (0)", 
    command=lambda: download_media("pdf"), 
    state="disabled"
)
pdf_download_button.pack(side="left", padx=5)

# Results Display
result_label = ctk.CTkLabel(root, text="Scraped Data:")
result_label.pack(pady=5)
result_text = ctk.CTkTextbox(root, width=800, height=250, state="disabled")
result_text.pack(pady=5, padx=10)

# Image Display
image_frame = ctk.CTkFrame(root)
image_frame.pack(pady=10)
img_label = ctk.CTkLabel(image_frame, text="No image found", width=300, height=300)
img_label.pack()
small_next_button = ctk.CTkButton(
    image_frame, 
    text="➔", 
    width=30, 
    height=30, 
    command=next_image, 
    state="disabled"
)
small_next_button.pack(pady=5)

# Navigation Buttons
nav_frame = ctk.CTkFrame(root)
nav_frame.pack(pady=5)
prev_button = ctk.CTkButton(nav_frame, text="Previous", command=prev_image)
prev_button.pack(side="left", padx=10)
next_button = ctk.CTkButton(nav_frame, text="Next", command=next_image)
next_button.pack(side="left", padx=10)

root.mainloop()