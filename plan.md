# Plan: Replace Mechanical Crawler with LLM Agent (Claude API)

## Overview
Replace `crawl_for_arcgis()` in `gov_arcgis_scanner.py` with an LLM-driven navigation agent that uses the Claude API to intelligently decide which links to follow when searching for ArcGIS REST endpoints on government websites.

## Architecture

**Fetching stays the same:** `requests` + BeautifulSoup (gov sites are server-rendered HTML).
**Navigation logic changes:** Instead of keyword substring matching, Claude reads the page links and picks the most promising ones to follow.

## Implementation Steps

### 1. Add `anthropic` dependency
- Add `anthropic>=0.49` to `requirements.txt`

### 2. Add LLM configuration to `gov_arcgis_scanner.py`
- Add `ANTHROPIC_API_KEY` from environment variable
- Add model config (default: `claude-sonnet-4-6` — fast and cheap for link selection)
- Add a toggle `USE_LLM_CRAWLER = True` so it can be disabled if no API key is set

### 3. Create `llm_crawl_for_arcgis()` function
Replace the current `crawl_for_arcgis()` with a new implementation:

**Flow:**
1. **Fast-path probe** common subdomains first (no LLM needed — cheap/fast)
2. If not found → fetch homepage with `requests`, parse with BeautifulSoup
3. Extract all `<a href>` links with their display text
4. Send links + crawler guide context to Claude via API
5. Claude returns a ranked list of URLs to follow (structured JSON output)
6. Fetch those pages, extract links, repeat
7. At each page, scan for ArcGIS target patterns (same regex logic as now)
8. Stop when target found or max depth/pages exceeded

**Claude prompt structure:**
- System message: Full crawler guide (allowed terms, exclusion list, target patterns)
- User message: Current page URL + list of all links found (text + href)
- Response format: JSON array of URLs to follow, ranked by likelihood

### 4. Update `scan()` to use the new crawler
- Replace the `crawl_for_arcgis()` call at line 1422 with `llm_crawl_for_arcgis()`
- Fall back to `guess_arcgis_urls()` if LLM crawl fails (same as now)
- If no API key is configured, fall back to the old mechanical crawler

### 5. Add API key configuration to web UI
- Add an environment variable `ANTHROPIC_API_KEY` check on startup
- Log a warning if not set (scanner still works in direct mode without it)
- No UI changes needed — the key is server-side only

## Files Modified
- `requirements.txt` — add `anthropic` dependency
- `gov_arcgis_scanner.py` — replace `crawl_for_arcgis()` with LLM agent version

## Files NOT modified
- `web_app.py` — no changes needed (calls `scan()` which handles everything)
- `docs/arcgis_rest_crawler_guide.md` — already has the prompt template, used as-is

## Cost/Performance Considerations
- Using `claude-sonnet-4-6` (fast, cheap) — each navigation decision is ~500-2000 input tokens
- Typical scan: 3-8 LLM calls (one per page visited) ≈ $0.01-0.05 per scan
- Fast-path probe runs first with zero LLM cost
- Max depth and max pages limits still enforced
