# AI Site Monitor v2 (Gemini 1.5 Flash)
# Main monitoring script for website keyword tracking

import os
import requests
import time
import json
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import generativeai as genai

# === Load config.yml ===
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yml")

with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

sites = config.get("sites", [])
keywords = config.get("keywords", [])
batch_size = config.get("batch_size", 50)
max_pages = config.get("max_pages_per_site", 5)
text_limit = config.get("text_limit", 2000)
timeout = config.get("timeout", 15)
max_concurrent = config.get("max_concurrent", 5)
retry_count = config.get("retry_count", 2)
model_name = config.get("gemini_model", "gemini-1.5-flash")

# === Gemini API setup ===
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ Missing GEMINI_API_KEY environment variable in GitHub Secrets.")

genai.configure(api_key=api_key)

# === Functions ===
def fetch_site(url):
    """Fetch page content with retries."""
    for attempt in range(retry_count):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text[:text_limit]
        except Exception as e:
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                print(f"[!] Failed to fetch {url}: {e}")
                return None


def analyze_with_gemini(site_data):
    """Use Gemini to analyze website content for promotions."""
    prompt = f"""
You are an AI website monitor. Analyze this site content and summarize any promotions, sales, or offers found.
Highlight specific details like product type, discount percent, or expiration date.
Return your findings in a clear and concise bullet list.

Site URL: {site_data['url']}
Content Sample:
{site_data['content']}
"""

    model = genai.GenerativeModel(model_name)
    result = model.generate_content(prompt)
    return result.text.strip() if result and result.text else "No promo info detected."


def monitor_sites():
    results = []

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_site = {executor.submit(fetch_site, site["url"]): site for site in sites}
        for future in as_completed(future_to_site):
            site = future_to_site[future]
            content = future.result()
            if content:
                site_data = {"url": site["url"], "content": content}
                analysis = analyze_with_gemini(site_data)
                results.append({"url": site["url"], "analysis": analysis})
            else:
                results.append({"url": site["url"], "analysis": "Failed to fetch site content."})

    return results


# === Main execution ===
if __name__ == "__main__":
    print("🚀 Running AI Site Monitor v2 (Gemini 1.5 Flash)...")
    start_time = time.time()

    results = monitor_sites()

    output_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"results_{int(time.time())}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"✅ Monitoring complete. {len(results)} sites checked in {time.time() - start_time:.1f}s")
    print(f"🗂 Results saved to: {output_path}")
