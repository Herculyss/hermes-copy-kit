# CopySnap

CopySnap is a lightweight product for generating marketing copy and 30-second video scripts with AI.

## What it does
- POST /generate-copy returns 5 ready-to-use copy variations
- POST /generate-script returns a 30-second script with Hook, Problem, Solution, and CTA
- landing/ contains a static frontend ready for Netlify

## Project structure
- app/ — FastAPI application
- landing/ — static landing page
- tests/ — API tests
- gumroad-copy.md — ready-to-paste Gumroad copy
- netlify.toml — Netlify publish config

## Local run
1. Install dependencies:
   python3 -m pip install -r requirements.txt
2. Export your key:
   export OPENROUTER_API_KEY="your_key"
3. Start the API:
   python3 -m uvicorn app.main:app --reload

## Branding
Product name: CopySnap
