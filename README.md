# Jewellery Address Verifier Pro

An enterprise-grade desktop application to verify and enrich jewellery shop addresses using Google Places API, Geocoding, Playwright-based web scraping, and a fallback web search.

## Features
- Multi-tier search pipeline (Google API -> Google Maps Scraper -> Google Search).
- Intelligent Verification Engine with weighted confidence scoring.
- Caching to minimize redundant API calls.
- Concurrency and Resume-from-crash capabilities.
- Professional Dark Theme Desktop UI.

## Requirements

- Python 3.11 or later
- Windows 10/11 recommended
- Git (optional, for cloning the repository)
- Internet access for Playwright and Google API access

## Installation

1. Clone or download this repository.
2. Install Python 3.11+.
3. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
4. Install Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Install Playwright browsers:
   ```powershell
   .venv\Scripts\playwright install chromium
   ```

## Configuration

1. Copy `.env.example` to `.env`.
2. Open `.env` and add your Google API key:
   ```env
   GOOGLE_API_KEY=your_api_key
   ```
3. If you do not have a Google API key or billing is disabled, the app will still run in Playwright-only mode.

## Project structure

- `main.py` — application orchestrator and UI runner
- `maps_scraper.py` — Google Maps scraping and Playwright automation
- `places_api.py` — Google Places API search fallback
- `geocoding.py` — Google Geocoding enrichment
- `excel_handler.py` — input/output Excel handling
- `models/shop.py` — shop data model
- `logger.py` — centralized logging setup
- `config.py` — connection mode and API helpers
- `constants.py` — shared constants and statuses

## Usage

1. Run the application:
   ```powershell
   python main.py
   ```
2. Select the input Excel file containing at least these columns:
   - `Shop Name + Old Address`
   - `District`
3. Choose an output directory.
4. Click `Start`.

## Output

The tool exports an updated Excel workbook to the selected output folder. If the default workbook is locked, the app falls back to a timestamped filename.

## Build executable

To build a standalone Windows executable:
```powershell
python build.py
```
The generated files will be placed in the `dist/` folder.
