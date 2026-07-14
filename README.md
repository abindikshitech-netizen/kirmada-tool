# Jewellery Address Verifier Pro

An enterprise-grade desktop application to verify and enrich jewellery shop addresses using Google Places API, Geocoding, Playwright-based web scraping, and a fallback web search.

## Features
- Multi-tier search pipeline (Google API -> Google Maps Scraper -> Google Search).
- Intelligent Verification Engine with weighted confidence scoring.
- Caching to minimize redundant API calls.
- Concurrency and Resume-from-crash capabilities.
- Professional Dark Theme Desktop UI.

## Installation

1. Clone or download this repository.
2. Install Python 3.11+.
3. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Install Playwright browsers:
   ```bash
   playwright install chromium
   ```

## Configuration

1. Copy `.env.example` to `.env`.
2. Add your Google Places/Geocoding API Key:
   ```env
   GOOGLE_API_KEY=your_api_key
   ```
   *(Alternatively, the UI will prompt for it on the first run and save it securely).*

## Usage

1. Run the application:
   ```bash
   python main.py
   ```
2. Select the input Excel file (with columns `Shop Name + Old Address` and `District`).
3. Select an output folder.
4. Click "Start".

## Build Executable

To generate a standalone Windows executable:
```bash
python build.py
```
The output will be available in the `dist/` folder.
