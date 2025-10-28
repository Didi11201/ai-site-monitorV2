import os
import time
import yaml
import json
import asyncio
import aiohttp
from datetime import datetime
from google import generativeai as genai

# -------------------------------
# Load configuration
# -------------------------------
CONFIG_PATH = "config.yml"
with open(CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f)

SITES = config.get("sites", [])
KEYWORDS = config.get("keywords", [])
MODEL = config.get("gemini_model", "gemini-1.5-flash")

# -------------------------------
# Gemini API setup
# -------------------------------
api_key = os.getenv("GEMINI_API_KEY") or config.get("gemini_api_key")
if not api_key:
    raise ValueError("❌ Missing Gemini API key. Please set GEMINI_API_KEY in Secrets or config.yml")

genai.configure(api_key=api_key)
model = genai.GenerativeModel(MODEL)

# -------------------------------
# Scrape & analyze
# -------------------------------
async def fetch(session, url, timeout):
    try:
        async with session.get(url, timeout=timeout) as response:
            text = await response.text()
            return text
    except Exception as e:
        return f"ERROR: {e}"

async def monitor_site(session, site):
    url = site["url"]
    print(f"🔍 Checking {url}")
    html = await fetch(session, url, config.get("timeout", 15))
    if html.startswith("ERROR:"):
        return {"url": url, "analysis": html}

    prompt = f"""
    You are an assistant analyzing website content for promotions.
    Site: {url}
    Look for words like: {', '.join(KEYWORDS)}.
    Summarize any promotions, discounts, or offers in bullet points.
    Output in concise, plain English.
    """
    try:
        result = model.generate_content(prompt + "\n\nContent:\n" + html[:config.get("text_limit", 2000)])
        summary = result.text.strip() if result.text else "No clear promotions found."
    except Exception as e:
        summary = f"Error analyzing site: {e}"

    return {"url": url, "analysis": summary}

async def main():
    start_time = time.time()
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        tasks = [monitor_site(session, site) for site in SITES]
        results = await asyncio.gather(*tasks)

    timestamp = int(time.time())
    json_path = os.path.join(results_dir, f"results_{timestamp}.json")
    html_path = os.path.join(results_dir, f"report_{timestamp}.html")

    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # -------------------------------
    # Generate HTML report
    # -------------------------------
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>AI Site Monitor Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #fafafa;
                color: #333;
            }}
            h1 {{ color: #0077cc; }}
            .site {{
                background: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            }}
            .url {{ font-weight: bold; color: #222; }}
            pre {{ white-space: pre-wrap; word-wrap: break-word; }}
        </style>
    </head>
    <body>
        <h1>🌐 AI Site Monitor Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
    """

    for r in results:
        html_content += f"""
        <div class="site">
            <p class="url">{r['url']}</p>
            <pre>{r['analysis']}</pre>
        </div>
        """

    html_content += "</body></html>"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Monitoring complete. {len(results)} sites checked in {time.time() - start_time:.1f}s")
    print(f"🗂 Results saved to: {json_path}")
    print(f"📄 HTML report saved to: {html_path}")

if __name__ == "__main__":
    asyncio.run(main())
