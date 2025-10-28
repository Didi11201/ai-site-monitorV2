import os
import yaml
import time
import json
import csv
import aiohttp
import asyncio
import google.generativeai as genai
from datetime import datetime

# === 加载配置文件 ===
CONFIG_PATH = "config.yml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

API_KEY = os.getenv("GEMINI_API_KEY") or config.get("gemini_api_key")
OUTPUT_DIR = config.get("output_dir", "results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("🚀 [启动监测程序]")
print(f"加载配置文件: {CONFIG_PATH}")
print(f"目标网站数量: {len(config['sites'])}")
print(f"关键词列表: {config['keywords']}")

# === Gemini 初始化与测试 ===
print("\n🔍 [检测 Gemini API 连接状态]")

if not API_KEY:
    print("❌ 未找到 Gemini API Key，请检查 GitHub Secrets 或 config.yml。")
    exit(1)

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(config.get("gemini_model", "gemini-1.5-flash"))
    test_response = model.generate_content("Say hi if Gemini is working.")
    print("✅ Gemini API 正常连接，测试回复:", test_response.text[:100])
except Exception as e:
    print("❌ Gemini 连接失败:", e)
    exit(1)

# === 异步网站监测逻辑 ===
async def fetch_site(session, url, timeout):
    try:
        async with session.get(url, timeout=timeout) as resp:
            text = await resp.text()
            return text[:config["text_limit"]]
    except Exception as e:
        print(f"⚠️ {url} 访问失败: {e}")
        return ""

async def analyze_site(model, url, html, keywords):
    """调用 Gemini 分析网站是否包含关键词"""
    if not html.strip():
        return False, []

    prompt = f"""
你是一位网站促销内容检测助手。
以下是网站 HTML 内容，请判断是否包含以下关键词（不区分大小写）：
{keywords}

HTML:
{html[:2000]}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.lower()
        found = [kw for kw in keywords if kw.lower() in text]
        return bool(found), found
    except Exception as e:
        print(f"⚠️ Gemini 分析 {url} 时出错: {e}")
        return False, []

async def monitor_sites():
    timeout = aiohttp.ClientTimeout(total=config.get("timeout", 15))
    results = []
    total_found = 0

    async with aiohttp.ClientSession() as session:
        for site in config["sites"]:
            url = site["url"]
            print(f"\n🌐 正在检测: {url}")

            html = await fetch_site(session, url, timeout)
            has_promo, found_keywords = await analyze_site(model, url, html, config["keywords"])
            total_found += int(has_promo)

            results.append({
                "site": url,
                "has_promo": has_promo,
                "found_keywords": ", ".join(found_keywords),
                "checked_at": datetime.utcnow().isoformat()
            })

            if has_promo:
                print(f"✅ {url} 检测到关键词: {found_keywords}")
            else:
                print(f"❌ {url} 未发现促销关键词")

    print(f"\n🎯 检测完成，总计 {len(results)} 个网站，检测到 {total_found} 个有促销内容。")

    # === 保存结果 ===
    json_path = os.path.join(OUTPUT_DIR, "results.json")
    csv_path = os.path.join(OUTPUT_DIR, "results.csv")

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(results, jf, ensure_ascii=False, indent=2)

    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        writer = csv.DictWriter(cf, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    print(f"\n📁 结果已保存到: {OUTPUT_DIR}/results.json 和 results.csv")

# === 主程序入口 ===
if __name__ == "__main__":
    asyncio.run(monitor_sites())
