# Markaroo Project Plan — v3 Architecture Refactor

## Application Purpose

Markaroo is a web application that discovers and catalogs GIS feature layers
from local government ArcGIS REST Services directories. Given a jurisdiction
name and/or website URL, it finds the ArcGIS REST Services directory, enumerates
all feature layers, filters them using planning-domain keywords from
`docs/planning-layer-pattern-skill-v2.md`, and exports a structured table.

---

## Requirements Restated

### Core Workflow
1. **Path A (Direct URL):** User provides a known ArcGIS REST Services directory
   URL (e.g., `https://gis.example.gov/arcgis/rest/services`). The app
   enumerates all layers, filters by planning keywords, and produces the output
   table. This path works today and must be preserved as-is.

2. **Path B (Discovery via LLM Web Search):** User provides a jurisdiction name
   and/or homepage URL. The app uses the Anthropic API (Claude + web_search tool)
   to find either:
   - **(a)** The jurisdiction's ArcGIS REST Services directory URL, OR
   - **(b)** At least one individual feature layer URL from that directory
     (e.g., `https://services8.arcgis.com/.../Address%20Point%20Public%20Safety/FeatureServer`),
     from which the REST directory root is derived by truncating at `/services/`.

3. **No web crawling.** The mechanical crawler (Tier 3) is **removed entirely**.
   If the LLM search fails, the scan reports failure — no fallback to crawling.

### What to Retain (Working Features)
- **Security:** URL validation, SSRF protection (`is_safe_url()`), prompt
  injection sanitization, API key handling, job ID validation, path traversal
  protection on downloads, XSS prevention in UI.
- **Path A direct-URL mode** — unchanged.
- **Table schema format:** GIS Layer Name | Source System | Collection | API
  Endpoint | Time Period | Update Frequency | Notes
- **Download function:** Excel (.xlsx) and Markdown (.md) export.
- **Progress status:** Real-time SSE streaming with log/stat/error/done events.
- **Progress summary:** Statistics cards + summary table after scan completes.
- **Web UI:** Flask single-page app with tabs (Progress, Results, Summary),
  status spinner, download buttons. Preserve current look and feel.
- **Tier 1 fast-path probe** (`guess_arcgis_urls()`) — keep as free first attempt.
- **Layer filtering/scoring** from planning-layer-pattern-skill-v2.md — keep.
- **Deduplication** — keep.

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| Tier 3 crawler | `crawl_for_arcgis()` + `load_crawler_guide()` | **Removed** |
| Tier 2 LLM search | Searches only for REST directory URL | Searches for REST directory **OR** individual feature layers |
| URL extraction | Only looks for `/arcgis/rest/services` root | Also extracts root from feature layer URLs (truncate at `/services/`) |
| Failure mode | Falls back to crawler | Reports "not found" — no crawler fallback |
| Crawler guide doc | `docs/arcgis_rest_crawler_guide.md` loaded at runtime | File remains for reference but code no longer loads it |
| UI mode selector | 3 modes: direct, homepage, gis_page | 2 modes: direct, discovery (LLM search) |
| User prompts | Crawler asks "try patterns / enter URL / stop" at max depth | Removed — LLM search either succeeds or reports failure |

---

## Implementation Plan

### Phase 1: Remove Mechanical Crawler (Tier 3)

**Files:** `gov_arcgis_scanner.py`

1. Delete `crawl_for_arcgis()` function (~130 lines)
2. Delete `load_crawler_guide()` function (~65 lines)
3. Delete `GIS_LINK_KEYWORDS` and `LINK_EXCLUSION_KEYWORDS` lists used by crawler
4. Remove `_CRAWLER_GUIDE_PATH` constant
5. Remove all `crawl_for_arcgis()` fallback calls in `llm_search_for_arcgis()`:
   - Lines where no API key → was crawler fallback → now return empty set with log message
   - Lines where no anthropic package → was crawler fallback → now return empty set
   - Lines where LLM errors → was crawler fallback → now return empty set
   - Lines where LLM returns no results → was crawler fallback → now return empty set
6. Remove the mid-scan user prompt that offered "try patterns / enter URL / stop"
   (this was only used by the crawler at max depth)
7. Remove BeautifulSoup import if no longer needed elsewhere (check first)

### Phase 2: Enhance LLM Search to Find Feature Layers

**Files:** `gov_arcgis_scanner.py`

1. Update `_build_llm_search_system_prompt()`:
   - Add instruction telling the LLM it can return EITHER a REST directory URL
     OR individual feature layer URLs (FeatureServer/MapServer endpoints)
   - Add examples of what feature layer URLs look like
   - Add instruction to search for common planning layer names from the v2 doc
     combined with the jurisdiction name (e.g., "Milpitas zoning FeatureServer")
   - Keep all existing URL pattern guidance

2. Update `_parse_llm_search_response()`:
   - Already extracts URLs via regex — ensure the regex catches both
     `/rest/services` root URLs and `/rest/services/.../FeatureServer` URLs

3. Update `llm_search_for_arcgis()`:
   - After collecting URLs from LLM, classify each as either:
     - **Root directory** (ends at `/services` or `/services/`)
     - **Feature layer** (contains `/FeatureServer` or `/MapServer` after `/services/`)
   - For feature layer URLs, extract the root directory by truncating at `/services/`
     (e.g., `https://services8.arcgis.com/.../ArcGIS/rest/services/LayerName/FeatureServer`
     → `https://services8.arcgis.com/.../ArcGIS/rest/services/`)
   - Return the set of unique root directory URLs (deduplicated)

4. Update the user prompt in `llm_search_for_arcgis()`:
   - Include specific planning-domain search terms from the v2 doc
   - Instruct the LLM to also try searching for feature layer names like
     "Zoning", "Parcels", "Land Use" combined with jurisdiction name

### Phase 3: Simplify UI Modes

**Files:** `web_app.py`

1. Remove `gis_page` mode from the mode selector
2. Rename `homepage` mode to `discovery` (or keep "homepage" internally)
3. Update validation logic for the simplified 2-mode system
4. Update UI labels and descriptions
5. Remove any crawler-specific progress messages from UI JavaScript

### Phase 4: Clean Up Dead Code

**Files:** `gov_arcgis_scanner.py`, `web_app.py`

1. Remove any remaining references to crawler functions or variables
2. Remove `InteractionRequest` usage if only used by crawler prompts
   (check if Path A or other code uses it first — keep if still needed)
3. Verify all imports are still needed

### Phase 5: Test & Verify

1. Confirm Path A (direct URL) still works end-to-end
2. Confirm Path B (LLM discovery) works with a known jurisdiction
3. Confirm no crawler code is reachable
4. Confirm downloads (xlsx, md) still work
5. Confirm progress streaming still works

---

## Files Affected

| File | Changes |
|------|---------|
| `gov_arcgis_scanner.py` | Remove crawler, enhance LLM search, extract roots from feature layer URLs |
| `web_app.py` | Simplify modes, remove crawler UI references |
| `docs/planning-layer-pattern-skill-v2.md` | No changes (reference doc) |
| `docs/arcgis_rest_crawler_guide.md` | No code changes; file stays for reference |

---

## Risk Mitigations

- **LLM search fails for a jurisdiction:** User can always fall back to Path A
  if they can manually find the REST URL. The UI should clearly communicate
  this option when discovery fails.
- **Feature layer URL format varies:** Use robust regex and normalize with
  `_normalize_rest_directory()` which already handles this.
- **Token cost:** LLM search uses claude-sonnet-4-6 by default (cost-effective).
  Max 6 API calls per search. No change from current behavior.
