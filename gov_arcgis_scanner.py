#!/usr/bin/env python3
"""
Government ArcGIS Feature Layer Scanner
========================================
Searches a local government website for ArcGIS REST Services Directory links,
filters for planning/development-related feature layers, deduplicates, and
exports results to Excel and Markdown.

Designed to run from a private intranet in production.
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 20  # seconds
MAX_CRAWL_PAGES = 120  # limit pages crawled on the government site
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT}

# ArcGIS REST Services Directory URL patterns
ARCGIS_REST_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]+/arcgis/rest/services", re.IGNORECASE),
    re.compile(r"https?://services\d*\.arcgis\.com/[A-Za-z0-9]+/ArcGIS/rest/services", re.IGNORECASE),
    re.compile(r"https?://[^\s\"'<>]+/rest/services(?:/|$)", re.IGNORECASE),
]

# Patterns for links that lead *toward* GIS / mapping content
GIS_LINK_KEYWORDS = [
    "gis", "map", "mapping", "interactive map", "webmap", "arcgis",
    "geographic", "geospatial", "open data", "data hub", "hub",
    "experience.arcgis.com", "arcgis.com",
]

# Map-service-level keywords (folder or service name) for planning/dev layers
SERVICE_KEYWORDS = [
    "planning", "community development", "commdev", "development",
    "zoning", "land use", "landuse", "community", "neighborhood",
    "building", "permits", "code enforcement",
]

# Feature-layer-level keywords we want to keep
LAYER_KEYWORDS = [
    "parcel", "zoning", "overlay", "planned development", "pud",
    "master plan", "land use", "landuse", "address", "hazard",
    "neighborhood", "floodplain", "flood", "zone", "planning area",
    "assessor", "historical district", "historic district", "greenway",
    "annexation", "subdivision", "plat", "comprehensive plan",
    "future land use", "entitlement", "setback", "corridor",
]

# Layer-name patterns to EXCLUDE (rasters, imagery, lidar, etc.)
EXCLUDE_PATTERNS = [
    re.compile(r"\b(raster|image|imagery|aerial|lidar|ortho|dem|elevation|hillshade|basemap|tile|cache)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Progress tracker (console-based for intranet/headless use)
# ---------------------------------------------------------------------------

class ProgressTracker:
    """Progress reporter that supports both console and callback modes."""

    def __init__(self, callback=None):
        self.steps: list[str] = []
        self.stats: dict[str, int] = defaultdict(int)
        self._callback = callback

    def log(self, message: str):
        self.steps.append(message)
        print(f"  [*] {message}")
        if self._callback:
            self._callback("log", message)

    def stat(self, key: str, value: int):
        self.stats[key] = value
        if self._callback:
            self._callback("stat", f"{key}: {value}")

    def summary(self):
        print("\n" + "=" * 60)
        print("  SCAN SUMMARY")
        print("=" * 60)
        for k, v in self.stats.items():
            print(f"  {k}: {v}")
        print("=" * 60 + "\n")
        if self._callback:
            self._callback("summary", json.dumps(dict(self.stats)))

    def reset(self, callback=None):
        """Reset state for a new scan run."""
        self.steps.clear()
        self.stats.clear()
        self._callback = callback


# Module-level default instance (used by CLI mode)
progress = ProgressTracker()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """GET with retries and error handling."""
    for attempt in range(3):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
    return None


# ---------------------------------------------------------------------------
# Step 1 – Crawl government site to find ArcGIS REST endpoints
# ---------------------------------------------------------------------------

def extract_arcgis_rest_urls(text: str) -> set[str]:
    """Pull ArcGIS REST Services Directory URLs from raw text."""
    urls: set[str] = set()
    for pat in ARCGIS_REST_PATTERNS:
        for m in pat.finditer(text):
            url = m.group(0).rstrip("/")
            # Normalise to the root services directory
            idx = url.lower().find("/rest/services")
            if idx != -1:
                url = url[: idx + len("/rest/services")]
            urls.add(url)
    return urls


def crawl_for_arcgis(start_url: str) -> set[str]:
    """
    Multi-step crawl:
      1. Scrape the start URL for ArcGIS links or GIS-related pages.
      2. Follow GIS-related pages one level deeper.
      3. Collect all ArcGIS REST Services Directory root URLs found.
    """
    progress.log(f"Starting crawl at {start_url}")
    visited: set[str] = set()
    to_visit: list[tuple[str, int]] = [(start_url, 0)]
    found_rest_urls: set[str] = set()
    base_domain = urlparse(start_url).netloc
    pages_crawled = 0

    while to_visit and pages_crawled < MAX_CRAWL_PAGES:
        url, depth = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        pages_crawled += 1

        resp = fetch(url)
        if resp is None:
            continue

        text = resp.text

        # Check for ArcGIS REST URLs in the page body
        rest_urls = extract_arcgis_rest_urls(text)
        if rest_urls:
            progress.log(f"  Found ArcGIS REST endpoint(s) on {url}")
            found_rest_urls.update(rest_urls)

        # If we haven't gone too deep, follow GIS-related links
        if depth < 3:
            soup = BeautifulSoup(text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                link_text = (a.get_text() or "").lower()
                full_url = urljoin(url, href)

                # Check the raw href for ArcGIS REST patterns
                rest_in_href = extract_arcgis_rest_urls(href) | extract_arcgis_rest_urls(full_url)
                if rest_in_href:
                    found_rest_urls.update(rest_in_href)
                    continue

                # Follow links that look GIS-related (same domain or arcgis.com)
                parsed = urlparse(full_url)
                is_same_domain = parsed.netloc == base_domain
                is_arcgis = "arcgis.com" in parsed.netloc

                if is_same_domain or is_arcgis:
                    href_lower = full_url.lower() + " " + link_text
                    if any(kw in href_lower for kw in GIS_LINK_KEYWORDS):
                        if full_url not in visited:
                            to_visit.append((full_url, depth + 1))

    progress.stat("Pages crawled", pages_crawled)
    progress.stat("ArcGIS REST endpoints found", len(found_rest_urls))

    if not found_rest_urls:
        progress.log("No ArcGIS REST endpoints discovered via crawl – trying common URL patterns")
        found_rest_urls = guess_arcgis_urls(start_url)

    return found_rest_urls


def guess_arcgis_urls(start_url: str) -> set[str]:
    """Brute-force common ArcGIS hosting patterns for the municipality."""
    parsed = urlparse(start_url)
    domain_parts = parsed.netloc.replace("www.", "").split(".")
    city_slug = domain_parts[0] if domain_parts else ""

    candidates = [
        f"https://gis.{parsed.netloc}/arcgis/rest/services",
        f"https://maps.{parsed.netloc}/arcgis/rest/services",
        f"https://{parsed.netloc}/arcgis/rest/services",
    ]
    # Try ArcGIS Online services patterns (services1-9)
    for i in range(1, 6):
        candidates.append(
            f"https://services{i}.arcgis.com/{city_slug}/ArcGIS/rest/services"
        )

    found: set[str] = set()
    for url in candidates:
        resp = fetch(url, timeout=10)
        if resp and resp.status_code == 200 and "services" in resp.text.lower():
            progress.log(f"  Guessed valid endpoint: {url}")
            found.add(url)
    return found


# ---------------------------------------------------------------------------
# Step 2 – Query ArcGIS REST API for folders, services, and layers
# ---------------------------------------------------------------------------

def query_rest_services(rest_url: str) -> list[dict]:
    """
    Walk the ArcGIS REST Services Directory. Returns a list of dicts:
      {service_name, service_url, layer_name, layer_id, layer_url,
       record_count, geometry_type, service_type}
    """
    progress.log(f"Querying ArcGIS REST directory: {rest_url}")
    layers: list[dict] = []

    # Fetch root
    root = fetch(f"{rest_url}?f=json")
    if root is None:
        progress.log(f"  Could not reach {rest_url}")
        return layers

    try:
        root_data = root.json()
    except (json.JSONDecodeError, ValueError):
        progress.log(f"  Invalid JSON from {rest_url}")
        return layers

    # Collect folders + root-level services
    folders = root_data.get("folders", [])
    services = root_data.get("services", [])

    # Also explore each folder
    for folder in folders:
        folder_url = f"{rest_url}/{folder}?f=json"
        resp = fetch(folder_url)
        if resp:
            try:
                folder_data = resp.json()
                services.extend(folder_data.get("services", []))
            except (json.JSONDecodeError, ValueError):
                pass

    progress.log(f"  Found {len(services)} services across {len(folders)} folders")

    for svc in services:
        svc_name = svc.get("name", "")
        svc_type = svc.get("type", "")

        # We only want FeatureServer or MapServer
        if svc_type not in ("FeatureServer", "MapServer"):
            continue

        svc_url = f"{rest_url}/{svc_name}/{svc_type}"
        resp = fetch(f"{svc_url}?f=json")
        if resp is None:
            continue

        try:
            svc_data = resp.json()
        except (json.JSONDecodeError, ValueError):
            continue

        svc_layers = svc_data.get("layers", [])
        for lyr in svc_layers:
            layer_name = lyr.get("name", "")
            layer_id = lyr.get("id", 0)
            layer_url = f"{svc_url}/{layer_id}"

            # Fetch layer details for record count and geometry
            lyr_detail = fetch(f"{layer_url}?f=json")
            record_count = None
            geom_type = ""
            if lyr_detail:
                try:
                    ld = lyr_detail.json()
                    geom_type = ld.get("geometryType", "")
                    # Try to get record count via query
                    count_resp = fetch(f"{layer_url}/query?where=1%3D1&returnCountOnly=true&f=json")
                    if count_resp:
                        count_data = count_resp.json()
                        record_count = count_data.get("count")
                except (json.JSONDecodeError, ValueError):
                    pass

            layers.append({
                "service_name": svc_name,
                "service_url": svc_url,
                "service_type": svc_type,
                "layer_name": layer_name,
                "layer_id": layer_id,
                "layer_url": layer_url,
                "record_count": record_count,
                "geometry_type": geom_type,
            })

    progress.stat("Total feature layers enumerated", len(layers))
    return layers


# ---------------------------------------------------------------------------
# Step 3 – Filter layers
# ---------------------------------------------------------------------------

def is_excluded(layer_name: str) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if pat.search(layer_name):
            return True
    return False


def matches_service_keywords(service_name: str) -> bool:
    sn = service_name.lower()
    return any(kw in sn for kw in SERVICE_KEYWORDS)


def matches_layer_keywords(layer_name: str) -> bool:
    ln = layer_name.lower()
    return any(kw in ln for kw in LAYER_KEYWORDS)


def filter_layers(layers: list[dict]) -> list[dict]:
    """Keep only planning/development-related feature layers, excluding rasters etc."""
    progress.log("Filtering layers by planning/development keywords…")

    # Separate into priority buckets
    priority_layers = []  # in a planning/dev service AND matches layer keywords
    secondary_layers = []  # matches layer keywords but service name doesn't match

    for lyr in layers:
        if is_excluded(lyr["layer_name"]):
            continue

        svc_match = matches_service_keywords(lyr["service_name"])
        lyr_match = matches_layer_keywords(lyr["layer_name"])

        if lyr_match:
            if svc_match:
                lyr["priority"] = 1
                priority_layers.append(lyr)
            else:
                lyr["priority"] = 2
                secondary_layers.append(lyr)

    result = priority_layers + secondary_layers
    progress.log(f"  {len(priority_layers)} layers in planning/dev services, "
                 f"{len(secondary_layers)} in other services")
    progress.stat("Layers after keyword filter", len(result))
    return result


# ---------------------------------------------------------------------------
# Step 4 – Deduplicate
# ---------------------------------------------------------------------------

def normalise_name(name: str) -> str:
    """Lowercase, strip non-alpha, collapse whitespace."""
    n = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return re.sub(r"\s+", " ", n).strip()


def names_are_similar(a: str, b: str, threshold: float = 0.65) -> bool:
    na, nb = normalise_name(a), normalise_name(b)
    if na == nb:
        return True
    # Check token overlap
    ta, tb = set(na.split()), set(nb.split())
    if ta and tb:
        overlap = len(ta & tb) / min(len(ta), len(tb))
        if overlap >= 0.6:
            return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


def deduplicate(layers: list[dict]) -> list[dict]:
    """
    Group layers with similar names and keep the best one per group.
    Priority: planning/dev service > highest record count.
    """
    progress.log("Deduplicating layers…")
    groups: list[list[dict]] = []

    for lyr in layers:
        placed = False
        for grp in groups:
            if names_are_similar(lyr["layer_name"], grp[0]["layer_name"]):
                grp.append(lyr)
                placed = True
                break
        if not placed:
            groups.append([lyr])

    deduped: list[dict] = []
    for grp in groups:
        # Sort: priority 1 first, then by record count descending
        grp.sort(key=lambda x: (x.get("priority", 99), -(x.get("record_count") or 0)))
        deduped.append(grp[0])

    removed = len(layers) - len(deduped)
    progress.log(f"  Removed {removed} duplicate layers")
    progress.stat("Layers after deduplication", len(deduped))
    progress.stat("Duplicates removed", removed)
    return deduped


# ---------------------------------------------------------------------------
# Step 5 – Output
# ---------------------------------------------------------------------------

def write_markdown(layers: list[dict], output_path: str):
    """Write the final table as a Markdown file."""
    lines = [
        "# Government ArcGIS Feature Layers – Scan Results\n",
        "| GIS Layer Name | Source System | Collection | API | Time Period | Update Frequency | Key Data Elements / Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for lyr in layers:
        name = lyr["layer_name"]
        api_url = lyr["layer_url"]
        lines.append(
            f"| {name} | Esri ArcGIS | API | {api_url} | Current | Ad Hoc | |"
        )
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    progress.log(f"Markdown written to {output_path}")


def write_excel(layers: list[dict], output_path: str):
    """Write the final table as an Excel workbook matching the schema."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Feature Layers"

    # Header styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")

    headers = [
        "GIS Layer Name",
        "Source System",
        "Collection",
        "API",
        "Time Period",
        "Update Frequency",
        "Key Data Elements / Notes",
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True)

    for row_idx, lyr in enumerate(layers, 2):
        ws.cell(row=row_idx, column=1, value=lyr["layer_name"])
        ws.cell(row=row_idx, column=2, value="Esri ArcGIS")
        ws.cell(row=row_idx, column=3, value="API")
        ws.cell(row=row_idx, column=4, value=lyr["layer_url"])
        ws.cell(row=row_idx, column=5, value="Current")
        ws.cell(row=row_idx, column=6, value="Ad Hoc")
        ws.cell(row=row_idx, column=7, value="")

    # Auto-width columns
    for col in ws.columns:
        max_len = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value or "")))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

    wb.save(output_path)
    progress.log(f"Excel written to {output_path}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def scan(website_url: str, output_dir: str = ".", progress_callback=None) -> dict:
    """
    Full pipeline: crawl → enumerate → filter → deduplicate → export.

    Args:
        website_url: Root URL of the government website.
        output_dir: Directory for output files.
        progress_callback: Optional callable(event_type, message) for live updates.

    Returns:
        dict with keys: xl_path, md_path, stats, error (if any).
    """
    progress.reset(callback=progress_callback)

    print("\n" + "=" * 60)
    print("  Government ArcGIS Feature Layer Scanner")
    print("=" * 60 + "\n")

    # Step 1 – find ArcGIS REST endpoints
    rest_urls = crawl_for_arcgis(website_url)
    if not rest_urls:
        progress.log("ERROR: Could not discover any ArcGIS REST Services Directory.")
        progress.summary()
        return {"error": "No ArcGIS REST endpoints found.", "stats": dict(progress.stats)}

    # Step 2 – enumerate all layers across discovered endpoints
    all_layers: list[dict] = []
    for rest_url in rest_urls:
        all_layers.extend(query_rest_services(rest_url))

    if not all_layers:
        progress.log("ERROR: No feature layers found at the discovered endpoints.")
        progress.summary()
        return {"error": "No feature layers found.", "stats": dict(progress.stats)}

    # Step 3 – filter
    filtered = filter_layers(all_layers)
    if not filtered:
        progress.log("WARNING: No layers matched planning/development keywords. "
                      "Outputting all non-excluded layers instead.")
        filtered = [l for l in all_layers if not is_excluded(l["layer_name"])]
        for l in filtered:
            l["priority"] = 99

    # Step 4 – deduplicate
    final_layers = deduplicate(filtered)

    # Step 5 – output
    os.makedirs(output_dir, exist_ok=True)

    domain = urlparse(website_url).netloc.replace("www.", "").split(".")[0]
    md_path = os.path.join(output_dir, f"{domain}_feature_layers.md")
    xl_path = os.path.join(output_dir, f"{domain}_feature_layers.xlsx")

    write_markdown(final_layers, md_path)
    write_excel(final_layers, xl_path)

    progress.stat("Final layers exported", len(final_layers))
    progress.summary()

    print(f"  Output files:")
    print(f"    Markdown : {os.path.abspath(md_path)}")
    print(f"    Excel    : {os.path.abspath(xl_path)}")
    print()

    return {
        "xl_path": os.path.abspath(xl_path),
        "md_path": os.path.abspath(md_path),
        "stats": dict(progress.stats),
        "layers": final_layers,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scan a local government website for ArcGIS planning/development feature layers."
    )
    parser.add_argument(
        "url",
        help="Root URL of the local government website (e.g. https://www.dublinohiousa.gov)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="Directory for output files (default: current directory)",
    )
    args = parser.parse_args()

    result = scan(args.url, args.output_dir)
    if result.get("error"):
        sys.exit(1)


if __name__ == "__main__":
    main()
