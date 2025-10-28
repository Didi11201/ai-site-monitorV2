#!/usr/bin/env python3
\"\"\"AI Site Monitor v2 (Gemini 1.5 Flash)
Asynchronous, batch + concurrent site scanner that:
- fetches homepage
- extracts internal links matching promo keywords
- fetches candidate pages (limited per-site)
- sends trimmed text (<= text_limit) to Gemini for JSON output
- writes results to results/results.json and results/results.csv
Configuration: config.yml or environment variables (.env)
\"\"\"

import os
import re
import asyncio
import json
import csv
from datetime import datetime
from urllib.parse import urlparse, urljoin

import aiohttp
from bs4 import BeautifulSoup
import yaml
from dotenv import load_dotenv
import google.generativeai as genai

# load .env if present
load_dotenv()

# load config
CONFIG_PATH = "config.yml"
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
else:
    cfg = {}

SITES = [s.get("url") if isinstance(s, dict) else s for s in cfg.get("sites", [])]
KEYWORDS = cfg.get("keywords", ["sale", "promo", "discount", "offer", "deal", "gift", "clearance"])
BATCH_SIZE = cfg.get("batch_size", 50)        # number of sites per batch
MAX_PAGES_PER_SITE = cfg.get("max_pages_per_site", 8)
TEXT_LIMIT = cfg.get("text_limit", 2000)
REQUEST_TIMEOUT = cfg.get("timeout", 15)
MAX_CONCURRENT = cfg.get("max_concurrent", 10)  # concurrency across all fetches
RETRY_COUNT = cfg.get("retry_count", 2)

# results paths
RESULTS_JSON = os.path.join("results", "results.json")
RESULTS_CSV = os.path.join("results", "results.csv")

# Gemini configuration via env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not set - AI calls will fail until you set the key in environment or GitHub Secrets.")
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = cfg.get("gemini_model", "gemini-1.5-flash")

# helpers
def domain_of(url):
    try:
        p = urlparse(url)
        return p.netloc
    except Exception:
        return ""

def normalize_link(href, base_url):
    return urljoin(base_url, href)

# simple function to trim large whitespace
def clean_text(s: str) -> str:
    return re.sub(r'\\s+', ' ', s).strip()

async def fetch_text(session: aiohttp.ClientSession, url: str, timeout=REQUEST_TIMEOUT):
    for attempt in range(RETRY_COUNT + 1):
        try:
            async with session.get(url, timeout=timeout) as resp:
                text = await resp.text(errors="ignore")
                return text
        except Exception as e:
            if attempt < RETRY_COUNT:
                await asyncio.sleep(1)
            else:
                return None

async def extract_candidate_links(session: aiohttp.ClientSession, site_url: str, max_links=30):
    html = await fetch_text(session, site_url)
    candidates = []
    domain = domain_of(site_url)
    if not html:
        return candidates
    soup = BeautifulSoup(html, "html.parser")
    # include homepage itself as a candidate
    candidates.append(site_url)
    for a in soup.find_all("a", href=True):
        href = a.get("href").strip()
        if not href:
            continue
        # normalize
        if href.startswith("http://") or href.startswith("https://"):
            link = href
        else:
            link = normalize_link(href, site_url)
        # only same-domain
        if domain_of(link) != domain:
            continue
        # keyword filter on path or anchor
        low = link.lower()
        text_anchor = (a.get_text() or "").lower()
        if any(k in low for k in KEYWORDS) or any(k in text_anchor for k in KEYWORDS):
            if link not in candidates:
                candidates.append(link)
        # avoid collecting too many
        if len(candidates) >= max_links:
            break
    return candidates

def prepare_prompt(text_snippet: str, site_url: str):
    # ask for strict JSON output
    prompt = f\"\"\"You are an automated promotion detection assistant for e-commerce websites.
Given the following extracted text from a web page (from {site_url}), decide whether the page contains an active promotion, discount, coupon, free gift, or limited-time deal.
Return ONLY a single-line JSON object with fields:
- has_promotion (true or false)
- promotion_summary (a short English summary if true, otherwise empty string)
Example:
{\"has_promotion\": true, \"promotion_summary\":\"20% off sitewide until Nov 30\"}
PAGE TEXT:
{text_snippet}
\"\"\"
    return prompt

def parse_ai_response(resp_text: str):
    # try to find a JSON object in the response
    try:
        start = resp_text.find(\"{\")
        end = resp_text.rfind(\"}\")
        if start != -1 and end != -1 and end > start:
            j = json.loads(resp_text[start:end+1])
            return {\"has_promotion\": bool(j.get(\"has_promotion\")), \"promotion_summary\": j.get(\"promotion_summary\", \"\")}
    except Exception:
        pass
    # fallback: search keywords
    low = resp_text.lower()
    has = any(k in low for k in KEYWORDS)
    return {\"has_promotion\": has, \"promotion_summary\": resp_text.strip()[:500]}

async def call_gemini(prompt: str):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        def sync_call():
            return model.generate_content(prompt)
        response = await asyncio.to_thread(sync_call)
        text = \"\"
        if hasattr(response, \"candidates\") and response.candidates:
            try:
                text = response.candidates[0].content[0].text
            except Exception:
                try:
                    text = response.candidates[0][\"content\"][0][\"text\"]
                except Exception:
                    text = str(response)
        else:
            text = str(response)
        return text
    except Exception as e:
        return f\"ERROR_AI: {e}\"

async def analyze_page(session, url):
    html = await fetch_text(session, url)
    if not html:
        return {\"url\": url, \"has_promotion\": False, \"promotion_summary\": \"\", \"status\": \"fetch_failed\"}
    text = clean_text(BeautifulSoup(html, \"html.parser\").get_text())
    snippet = text[:TEXT_LIMIT]
    prompt = prepare_prompt(snippet, url)
    ai_raw = await call_gemini(prompt)
    parsed = parse_ai_response(ai_raw)
    parsed.update({\"url\": url, \"status\": \"ok\"})
    return parsed

async def process_site(session, site_url):
    try:
        candidates = await extract_candidate_links(session, site_url, max_links=MAX_PAGES_PER_SITE)
        candidates = candidates[:MAX_PAGES_PER_SITE]
        tasks = [analyze_page(session, c) for c in candidates]
        results = []
        for i in range(0, len(tasks), MAX_CONCURRENT):
            chunk = tasks[i:i+MAX_CONCURRENT]
            res = await asyncio.gather(*chunk)
            results.extend(res)
        site_has = any(r.get(\"has_promotion\") for r in results)
        summaries = [r.get(\"promotion_summary\") for r in results if r.get(\"has_promotion")]
        return {\"site\": site_url, \"has_promotion\": site_has, \"promotion_summaries\": summaries, \"pages\": results, \"checked_at\": datetime.utcnow().isoformat()}
    except Exception as e:
        return {\"site\": site_url, \"has_promotion\": False, \"promotion_summaries\": [], \"error\": str(e), \"checked_at\": datetime.utcnow().isoformat()}

async def run_all(sites_list):
    all_results = []
    connector = aiohttp.TCPConnector(limit_per_host=10)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    sem = asyncio.Semaphore(MAX_CONCURRENT)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        async def sem_task(site):
            async with sem:
                return await process_site(session, site)
        tasks = [sem_task(site) for site in sites_list]
        for i in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[i:i+BATCH_SIZE]
            batch_res = await asyncio.gather(*batch)
            all_results.extend(batch_res)
    return all_results

def save_results_json(results_obj):
    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(results_obj, f, ensure_ascii=False, indent=2)

def save_results_csv(results_obj):
    os.makedirs(os.path.dirname(RESULTS_CSV), exist_ok=True)
    with open(RESULTS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["site", "has_promotion", "promotion_summaries", "checked_at"])
        for r in results_obj:
            writer.writerow([r.get("site"), r.get("has_promotion"), " || ".join(r.get("promotion_summaries", [])), r.get("checked_at")])

def load_sites_from_config():
    s = []
    raw = cfg.get("sites") or []
    for item in raw:
        if isinstance(item, dict):
            s.append(item.get("url"))
        elif isinstance(item, str):
            s.append(item)
    return s

def main():
    sites_list = load_sites_from_config()
    if not sites_list:
        print("No sites configured in config.yml. Please edit config.yml and add sites.")
        return
    results = asyncio.run(run_all(sites_list))
    save_results_json(results)
    save_results_csv(results)
    print(f"Completed checking {len(results)} sites. Results saved to {RESULTS_JSON} and {RESULTS_CSV}")

if __name__ == "__main__":
    main()
