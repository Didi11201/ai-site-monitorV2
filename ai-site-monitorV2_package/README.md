# AI Site Monitor v2 (Gemini)

This repository contains a ready-to-run AI-powered site monitor that:
- Scans a list of websites (homepages)
- Detects internal pages likely related to promotions (sale, promo, discount)
- Sends trimmed page text to Gemini 1.5 Flash and asks for JSON judgement
- Saves results to `results/results.json` and `results/results.csv`
- Designed to run on GitHub Actions (or locally)

## Quick start

1. Copy this repo to GitHub (or upload files).
2. Create a Google API key in Google AI Studio / Cloud (Gemini).
3. Add the key to your GitHub repository secrets: `GEMINI_API_KEY`.
4. Edit `config.yml` to list your target sites.
5. Run workflow manually in Actions or let schedule run it.

## Local run

1. Create a Python virtualenv and install deps:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` (or set environment variable):
```
GEMINI_API_KEY=your_api_key_here
```

3. Run:
```
python monitor.py
```

## Notes / Troubleshooting

- The script limits text to `text_limit` characters for each page to reduce API usage.
- It tries to detect internal links containing keywords; if missed, add pages directly to `config.yml`.
- Results saved under `results/` folder.
