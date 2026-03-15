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
import threading
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

# Suppress InsecureRequestWarning for government sites with bad SSL certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
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

# ---------------------------------------------------------------------------
# Tier 1 — Service Path Signals (per planning-layer-pattern-skill.md)
# ---------------------------------------------------------------------------

# Department identifiers in service path (+5 confidence)
TIER1_DEPARTMENT_TOKENS = [
    "comdev", "cdd", "planning", "landdev", "communitydevelopment",
    "community_development", "energov", "plu", "rois", "p_d", "cd",
]

# Land use / zoning service name tokens (+4 confidence)
TIER1_LANDUSE_TOKENS = [
    "zoning", "land_use", "landuse", "future_land_use", "general_plan",
    "residential_zoning", "masterplan", "master_plan", "master_planned",
    "historic_district", "nrhp", "subdivision", "tif_parcels", "tif_zones",
    "housing_element", "housingelement", "specific_plans", "specificplans",
    "precise_plan", "preciseplan", "opportunity_sites", "urban_growth",
    "ugb", "parcels", "form_based_code", "form.based.code",
    "comprehensive_plan", "flum", "special_area_plan", "mello_roos",
    "melloroos", "mello-roos", "zcu",
]

# Development / planning service name tokens (+3 confidence)
TIER1_DEVELOPMENT_TOKENS = [
    "development", "agreement", "growth", "plan", "development_agreement",
    "outside_development", "downtown", "dtmasterplan", "envision",
    "growth_framework", "corridor_plan", "sector_plan",
]

# Combined list for simple boolean check (backward compat)
SERVICE_KEYWORDS = (
    TIER1_DEPARTMENT_TOKENS + TIER1_LANDUSE_TOKENS + TIER1_DEVELOPMENT_TOKENS
)

# ---------------------------------------------------------------------------
# Tier 2 — Layer Name Keyword Signals (10 semantic clusters)
# ---------------------------------------------------------------------------

# Cluster A: Zoning and Land Use Regulation
CLUSTER_A = [
    "zoning", "zone", "zone overlay", "zone map", "overlay", "land use",
    "future land use", "general plan", "comprehensive plan", "flum",
    "planned development", "form-based code", "form based code", "infill",
    "residential zoning", "non attainment", "ugb", "urban growth boundary",
    "zoning code update", "zcu", "hillside code", "hillside regulation",
    "heights", "tree zone", "tree preservation",
    # California SB 9 / AB 2923
    "sb 9", "ab 2923", "two-unit overlay", "two unit overlay",
    "lot split zone", "lot split", "state density bonus", "density bonus",
    "ministerial zone", "ministerial",
    # ADU
    "adu overlay", "adu zone", "accessory dwelling", "junior adu", "adu",
    # Southeast
    "udo", "unified development ordinance", "tnd",
    "traditional neighborhood", "rural preservation",
    # Midwest
    "overlay district", "conservation district",
]

# Cluster B: Development Review and Entitlements
CLUSTER_B = [
    "subdivision", "subdivisions", "subdivision sections",
    "special use permit", "development agreement", "agreement area",
    "pace agreement", "tdr", "transfer of development rights",
    "tif", "tax increment", "annexation", "annex", "deannex",
    "outside development", "planned development", "planned unit development",
    "pud", "housing element", "housing element sites", "by-right",
    "opportunity sites", "project development", "project developments",
    "project pipeline", "innovation parcel",
    # Housing
    "bmr", "below market rate", "low income housing", "affordable housing",
    "cfd", "cfd parcels", "mello-roos", "mello_roos", "melloroos",
    # Southeast / Regional
    "vad", "voluntary agricultural district", "voluntary agricultural",
    # California RHNA
    "rhna", "rhna sites", "rhna allocation", "rezoning rhna",
    # Midwest
    "enterprise zone", "special assessment district", "tax abatement",
    # Texas
    "pdd", "planned development district", "sup", "specific use permit",
    "reinvestment zone", "tirz", "4b sales tax",
    # Southwest
    "pad", "planned area development",
    # General
    "conservation subdivision", "activity center",
    "plat", "entitlement", "setback", "permits",
]

# Cluster C: Comprehensive / Master Planning
CLUSTER_C = [
    "master plan", "master planned", "general plan", "comprehensive plan",
    "future land use", "growth framework", "character areas",
    "special area plan", "specific plans", "specific plan", "precise plan",
    "precise plan area", "civic master plan", "downtown plan",
    "town center plan", "viewplane", "mtn viewplane", "greenline",
    "sphere of influence", "urban growth boundary",
    "transit priority area", "high quality transit corridor", "hqtc",
    "transit buffer", "midtown boundary", "corridor plan", "corridor",
    "small area plan", "area plan", "sector plan",
    # Southwest
    "rural planning area", "thoroughfare plan",
]

# Cluster D: Historic Preservation
CLUSTER_D = [
    "historic district", "historic sites", "historic buildings",
    "historic inventory", "historical inventory", "historical district",
    "nrhp", "character areas", "landmark", "local historic district",
    "national historic district", "heritage district", "preservation district",
]

# Cluster E: Environmental Overlay (Planning-Regulated)
CLUSTER_E = [
    "stream margin", "wildfire hazard", "wui", "wildland-urban interface",
    "esa", "environmentally sensitive", "hallam bluff", "non attainment",
    "tree preservation", "tree canopy", "agricultural buffer",
    "conservation easement", "floodplain", "flood zone",
    # Regional
    "npdes buffer", "flood administration", "view corridor", "viewshed",
    "water rights overlay", "dark sky", "ceqa overlay",
]

# Cluster F: Cadastral and Property Reference
CLUSTER_F = [
    "parcels", "parcel", "assessor parcels", "assessor parcel", "pid",
    "tif parcels", "cfd parcels", "bmr parcels", "flood zone parcels",
    "religious parcel", "building footprints landuse", "lot",
    "parcel owner", "parcel report", "innovation parcel", "right of way",
    "section township range", "address",
]

# Cluster G: Administrative Geography
CLUSTER_G = [
    "neighborhoods", "neighborhood", "neighborhood boundary",
    "city limits", "wards", "council wards", "city boundary",
    "municipal boundary", "sphere of influence",
    "etj", "extraterritorial jurisdiction",
    "township", "greenway",
    "planning area",
]

# Cluster H: Regulatory Use Restrictions
CLUSTER_H = [
    "billboard buffer", "billboards exclusionary zone",
    "outdoor lighting code", "short term rental", "prohibited area",
    "resort hotels", "small cell wireless", "cell towers",
    "scenic byway", "pedestrian mall", "gaming overlay", "gaming district",
    "community residence", "symphony district", "alcohol buffer",
    "adult use overlay", "cannabis overlay", "noise contour",
    "military influence area",
]

# Cluster I: Hazards and Development Restrictions
CLUSTER_I = [
    "floodplain", "flood plain", "flood zone", "floodway", "flood area",
    "100 year flood", "100-year flood", "100 year floodway",
    "500 year flood", "500-year flood",
    "fema flood", "fema floodplain", "special flood hazard area", "sfha", "firm",
    "fire zone", "fire hazard", "fire buffer",
    "wildfire", "wildfire district", "wildfire zone", "wildfire hazard", "wui",
    "earthquake zone", "seismic zone", "seismic hazard",
    "liquefaction", "tsunami zone", "tsunami hazard", "geologic hazard",
    "steep slope", "slope restriction", "slope overlay", "landslide", "erosion zone",
    "contour", "10 foot contour", "100 foot contour", "topo contour",
    "wetlands", "wetland buffer", "wetland setback",
    "riparian buffer", "riparian zone", "riparian corridor",
    "stream buffer", "stream setback", "river buffer", "waterbody setback",
    "rivers", "streams", "ponds", "lakes", "waterbodies", "water bodies", "hydrology",
    "conservation easement", "easement",
    "agricultural district", "right to farm", "rtf zone", "rtf district", "farm buffer",
]

# Cluster J: Landmarks and Civic Features (supporting only — requires co-occurring signal)
CLUSTER_J = [
    "high school", "middle school", "elementary school", "public school",
    "school location", "school point", "school site",
    "parks", "park location", "park point",
    "civic area", "civic center", "city hall", "county hall", "county courthouse", "courthouse",
    "fire station", "police station", "library", "community center",
    "transit stop", "transit node", "bus stop", "light rail stop", "train station",
    "commuter rail", "airport",
    "rivers", "streams", "lakes", "lakefront", "waterfront", "water feature",
    "fountain", "playground", "ball field", "athletic field", "stadium", "sports complex",
    "recreation area", "open space", "greenway",
]

# Combined flat list for simple keyword matching (backward compat)
LAYER_KEYWORDS = (
    CLUSTER_A + CLUSTER_B + CLUSTER_C + CLUSTER_D +
    CLUSTER_E + CLUSTER_F + CLUSTER_G + CLUSTER_H +
    CLUSTER_I + CLUSTER_J
)

# ---------------------------------------------------------------------------
# Exclusion Signals — High-Confidence Non-Planning Indicators
# ---------------------------------------------------------------------------

# Service path exclusion tokens
EXCLUDE_SERVICE_TOKENS = [
    "pw_", "scl", "rtc_", "bus_stops", "live_scl", "dpw", "publicworks",
    "fd_", "phantoms", "fire_", "ems_",
    "live_clv_bus", "clv_bus", "business_license",
    "parks_protected", "pools_view", "community_centers_view",
    "utilities", "water_", "sewer_", "storm_", "stormwater_",
    "recycled_water", "lucity",
    "ccsd_schools", "privateschools",
    "police_", "mark43_",
]

# Layer name exclusion keywords
EXCLUDE_LAYER_KEYWORDS = [
    # Public Works / Transportation
    "streets", "major streets", "bike trails", "bicycle lane", "bicycle route",
    "equestrian trails", "trail crossing", "trailheads", "trail projects",
    "trails network", "bus stops", "pavement condition", "pavement index",
    "street sweeping", "guardrails", "handicap ramps", "street lights",
    "traffic signal", "truck routes", "crossroads", "street centerlines",
    "road closures",
    # Fire / Emergency
    "fire map", "phantoms", "emergency", "ems", "fire districts",
    "fire pre plan", "fire run", "fire stations", "fire incidents",
    "fire hydrants", "fire water points",
    # Business License
    "business licenses", "active business licenses",
    "gaming restricted", "gaming non-restricted",
    "alcohol on-premise", "alcohol off-premise",
    "massage establishment", "marijuana establishments",
    "daily labor service", "financial institution",
    "amusement park", "open air vending",
    "alcohol beverage control",
    # Parks (standalone)
    "pools", "community centers", "park lights", "park pathways",
    "park points",
    # Utilities
    "water hydrant", "water meter", "water service", "sewer", "sanitary",
    "storm drain", "recycled water", "irrigation controller",
    "backflow", "odor sample",
    # Schools (standalone)
    "ccsd schools", "private schools", "school points",
    # Police
    "police beats", "police traffic citations", "crime",
    "tiburon reporting districts",
    # Transportation
    "airports", "roads", "railroads",
]

# Raster/non-vector exclusion patterns
EXCLUDE_PATTERNS = [
    re.compile(r"\b(raster|image|imagery|aerial|lidar|ortho|dem|elevation|hillshade|basemap|tile|cache)\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Dynamic keyword loading from planning-layer-pattern-skill.md
# ---------------------------------------------------------------------------

# Path to the planning layer pattern skill document (in repo)
_SKILL_DOC_PATH = os.path.join(os.path.dirname(__file__), "docs", "planning-layer-pattern-skill.md")
# Path to the ArcGIS REST crawler guide (in repo)
_CRAWLER_GUIDE_PATH = os.path.join(os.path.dirname(__file__), "docs", "arcgis_rest_crawler_guide.md")


def _parse_keywords_from_table(md_text: str, section_heading: str) -> list[str]:
    """Extract tokens from a markdown table under a given heading.
    Looks for the first column (Token/Pattern) values."""
    keywords: list[str] = []
    in_section = False
    in_table = False
    for line in md_text.splitlines():
        stripped = line.strip()
        # Track headings
        if stripped.startswith("#"):
            if section_heading.lower() in stripped.lower():
                in_section = True
                in_table = False
                continue
            elif in_section and stripped.startswith("#"):
                # Hit next section at same or higher level
                in_section = False
                in_table = False
                continue
        if not in_section:
            continue
        # Detect table rows (skip header separator)
        if stripped.startswith("|") and not stripped.startswith("|---"):
            cols = [c.strip() for c in stripped.split("|")]
            cols = [c for c in cols if c]  # remove empty from leading/trailing |
            if len(cols) >= 1:
                token = cols[0]
                # Skip header row
                if token.lower() in ("token", "token / pattern", "layer name",
                                      "abbreviation", "term", "signal"):
                    continue
                # Clean up: remove backticks, markdown formatting
                token = token.replace("`", "").replace("*", "").strip()
                if not token:
                    continue
                # Split on " / " for multi-variant entries (e.g. "Zoning / ZONING")
                # and on " or " for alternatives
                variants = re.split(r"\s*/\s*|\s+or\s+", token)
                for v in variants:
                    v = v.strip().lower()
                    # Remove regex-style wildcards and parenthetical notes
                    v = re.sub(r"\(.*?\)", "", v).strip()
                    v = re.sub(r"\.\*", "", v).strip()
                    if v and len(v) > 1:
                        keywords.append(v)
    return keywords


def _parse_cluster_keywords(md_text: str, cluster_label: str) -> list[str]:
    """Extract keywords from a Cluster paragraph like 'Cluster A: ...'
    Keywords are listed after 'Keywords:' as comma-separated values."""
    keywords: list[str] = []
    in_cluster = False
    for line in md_text.splitlines():
        stripped = line.strip()
        if cluster_label.lower() in stripped.lower() and stripped.startswith("#"):
            in_cluster = True
            continue
        if in_cluster:
            if stripped.startswith("#"):
                break  # next section
            if "keywords:" in stripped.lower():
                # Parse comma-separated keywords after "Keywords:"
                kw_part = stripped.split(":", 1)[1] if ":" in stripped else stripped
                for kw in kw_part.split(","):
                    kw = kw.strip().strip("`").strip("*").strip()
                    # Remove regex-style patterns and parenthetical notes
                    kw = re.sub(r"\(.*?\)", "", kw).strip()
                    kw = re.sub(r"\.\*", " ", kw).strip()
                    if kw and len(kw) > 1:
                        keywords.append(kw.lower())
    return keywords


def reload_keywords_from_skill_doc():
    """
    Re-read the planning-layer-pattern-skill.md and update the module-level
    keyword lists. Called at the start of every scan so changes to the doc
    are picked up without restarting the server.
    """
    global TIER1_DEPARTMENT_TOKENS, TIER1_LANDUSE_TOKENS, TIER1_DEVELOPMENT_TOKENS
    global SERVICE_KEYWORDS
    global CLUSTER_A, CLUSTER_B, CLUSTER_C, CLUSTER_D, CLUSTER_E, CLUSTER_F
    global CLUSTER_G, CLUSTER_H, CLUSTER_I, CLUSTER_J, LAYER_KEYWORDS
    global EXCLUDE_SERVICE_TOKENS, EXCLUDE_LAYER_KEYWORDS

    if not os.path.isfile(_SKILL_DOC_PATH):
        return  # file not found — keep existing hardcoded defaults

    try:
        with open(_SKILL_DOC_PATH, "r", encoding="utf-8") as f:
            md = f.read()
    except OSError:
        return  # read error — keep defaults

    # --- Tier 1: Service path tokens ---
    dept = _parse_keywords_from_table(md, "Explicit Department Identifiers")
    if dept:
        TIER1_DEPARTMENT_TOKENS = dept

    landuse = _parse_keywords_from_table(md, "Land Use and Zoning Service Names")
    parcel = _parse_keywords_from_table(md, "Parcel and Property Services")
    if landuse or parcel:
        TIER1_LANDUSE_TOKENS = landuse + parcel

    dev = _parse_keywords_from_table(md, "Development Activity Services")
    historic = _parse_keywords_from_table(md, "Historic Preservation Services")
    if dev or historic:
        TIER1_DEVELOPMENT_TOKENS = dev + historic

    SERVICE_KEYWORDS = TIER1_DEPARTMENT_TOKENS + TIER1_LANDUSE_TOKENS + TIER1_DEVELOPMENT_TOKENS

    # --- Tier 2: Layer name clusters ---
    for label, attr in [
        ("Cluster A", "CLUSTER_A"), ("Cluster B", "CLUSTER_B"),
        ("Cluster C", "CLUSTER_C"), ("Cluster D", "CLUSTER_D"),
        ("Cluster E", "CLUSTER_E"), ("Cluster F", "CLUSTER_F"),
        ("Cluster G", "CLUSTER_G"), ("Cluster H", "CLUSTER_H"),
        ("Cluster I", "CLUSTER_I"), ("Cluster J", "CLUSTER_J"),
    ]:
        parsed = _parse_cluster_keywords(md, label)
        if parsed:
            globals()[attr] = parsed

    LAYER_KEYWORDS = (
        CLUSTER_A + CLUSTER_B + CLUSTER_C + CLUSTER_D +
        CLUSTER_E + CLUSTER_F + CLUSTER_G + CLUSTER_H +
        CLUSTER_I + CLUSTER_J
    )

    # --- Exclusion signals ---
    # Parse exclusion section tables/keywords
    excl_svc: list[str] = []
    excl_lyr: list[str] = []
    in_exclusion = False
    current_subsection = ""
    for line in md.splitlines():
        stripped = line.strip()
        if "## 4. Exclusion Signals" in stripped:
            in_exclusion = True
            continue
        if in_exclusion and stripped.startswith("## ") and "Exclusion" not in stripped:
            break
        if not in_exclusion:
            continue
        if stripped.startswith("###"):
            current_subsection = stripped
            continue
        # Parse "Service name tokens:" lines
        if "service name tokens:" in stripped.lower():
            tokens_part = stripped.split(":", 1)[1] if ":" in stripped else ""
            for t in tokens_part.split(","):
                t = t.strip().strip("`").strip()
                if t:
                    excl_svc.append(t.lower())
        # Parse "Layer name keywords:" lines
        if "layer name keywords:" in stripped.lower():
            kw_part = stripped.split(":", 1)[1] if ":" in stripped else ""
            for kw in kw_part.split(","):
                kw = kw.strip().strip("`").strip()
                if kw and len(kw) > 1:
                    excl_lyr.append(kw.lower())

    if excl_svc:
        EXCLUDE_SERVICE_TOKENS = excl_svc
    if excl_lyr:
        EXCLUDE_LAYER_KEYWORDS = excl_lyr


def load_crawler_guide() -> dict:
    """
    Load the ArcGIS REST crawler guide from the repo and return a config dict
    with allowed_terms (list[str]) and exclusion_terms (list[str]).
    """
    config = {"allowed_terms": [], "exclusion_terms": [], "max_depth": 5, "max_pages": 75}

    if not os.path.isfile(_CRAWLER_GUIDE_PATH):
        return config

    try:
        with open(_CRAWLER_GUIDE_PATH, "r", encoding="utf-8") as f:
            md = f.read()
    except OSError:
        return config

    # Parse code-fenced term lists under each CATEGORY section
    in_allowed = False
    in_exclusion = False
    in_code_block = False
    current_section = ""

    for line in md.splitlines():
        stripped = line.strip()

        # Track section headings
        if stripped.startswith("## Allowed Terms Lists"):
            in_allowed = True
            in_exclusion = False
            continue
        if stripped.startswith("## Exclusion List"):
            in_allowed = False
            in_exclusion = True
            continue
        if stripped.startswith("## ") and not stripped.startswith("### "):
            if stripped.startswith("## Allowed") or stripped.startswith("## Exclusion"):
                pass
            else:
                in_allowed = False
                in_exclusion = False
            continue

        # Track ENABLED flag
        if "**ENABLED:**" in stripped:
            if "`false`" in stripped.lower():
                current_section = "disabled"
            else:
                current_section = "enabled"
            continue

        # Track code blocks
        if stripped == "```":
            in_code_block = not in_code_block
            continue

        # Collect terms from code blocks
        if in_code_block and stripped and current_section != "disabled":
            term = stripped.lower()
            if in_allowed:
                config["allowed_terms"].append(term)
            elif in_exclusion:
                config["exclusion_terms"].append(term)

    return config


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
    last_error = None
    for attempt in range(3):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except requests.exceptions.SSLError:
            # Retry once without SSL verification for government sites
            # with misconfigured certificates
            try:
                r = session.get(url, timeout=timeout, allow_redirects=True,
                                verify=False)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last_error = f"SSL error and fallback failed: {e}"
                break
        except requests.exceptions.HTTPError as e:
            last_error = f"HTTP {r.status_code}"
            # Some government pages return 403 but still have usable content
            if r.status_code in (403, 406):
                return r
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
        except requests.exceptions.Timeout:
            last_error = "Request timed out"
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
        except requests.RequestException as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
    if last_error:
        progress.log(f"    ⚠ Fetch failed: {last_error}")
    return None


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------

def validate_url(url: str, mode: str = "homepage") -> dict:
    """
    Validate a URL before starting a scan.
    Returns dict with: valid (bool), message (str), status_code (int or None).
    """
    # Basic format check
    parsed = urlparse(url)
    if not parsed.scheme:
        return {"valid": False, "message": "URL must start with http:// or https://",
                "status_code": None}
    if parsed.scheme not in ("http", "https"):
        return {"valid": False, "message": f"Unsupported scheme '{parsed.scheme}'. Use http:// or https://",
                "status_code": None}
    if not parsed.netloc:
        return {"valid": False, "message": "URL has no domain name.",
                "status_code": None}

    # For direct mode, check that URL looks like an ArcGIS REST endpoint
    if mode == "direct":
        if "/rest/services" not in url.lower():
            return {"valid": False,
                    "message": "For Direct mode, URL should contain '/rest/services' "
                               "(e.g. https://gis.example.gov/arcgis/rest/services)",
                    "status_code": None}

    # Reachability check
    try:
        r = session.head(url, timeout=10, allow_redirects=True)
        if r.status_code < 400:
            return {"valid": True,
                    "message": f"URL is reachable (HTTP {r.status_code}).",
                    "status_code": r.status_code}
        # Some government sites block HEAD requests; retry with GET
        r = session.get(url, timeout=10, allow_redirects=True)
        if r.status_code < 400:
            return {"valid": True,
                    "message": f"URL is reachable (HTTP {r.status_code}).",
                    "status_code": r.status_code}
        return {"valid": False,
                "message": f"URL returned HTTP {r.status_code}.",
                "status_code": r.status_code}
    except requests.exceptions.SSLError:
        # Retry without SSL verification for misconfigured government certs
        try:
            r = session.head(url, timeout=10, allow_redirects=True, verify=False)
            if r.status_code < 400:
                return {"valid": True,
                        "message": f"URL is reachable (HTTP {r.status_code}, SSL certificate issue bypassed).",
                        "status_code": r.status_code}
            return {"valid": False,
                    "message": f"URL returned HTTP {r.status_code} (SSL certificate issue bypassed).",
                    "status_code": r.status_code}
        except requests.RequestException as e:
            return {"valid": False,
                    "message": f"SSL certificate error and fallback failed: {e}",
                    "status_code": None}
    except requests.ConnectionError:
        return {"valid": False, "message": "Could not connect to the server. Check the URL and your network.",
                "status_code": None}
    except requests.Timeout:
        return {"valid": False, "message": "Connection timed out. The server may be down.",
                "status_code": None}
    except requests.RequestException as e:
        return {"valid": False, "message": f"Request failed: {e}",
                "status_code": None}


# ---------------------------------------------------------------------------
# Interaction helper (for prompting user mid-scan)
# ---------------------------------------------------------------------------

class InteractionRequest:
    """Allows the scanner to pause and ask the user a question."""

    def __init__(self):
        self._response_event = threading.Event()
        self._response_value: Optional[str] = None

    def ask(self, prompt_callback, question: str, options: list[str]) -> str:
        """
        Send a prompt to the user via the progress callback and block
        until a response is received.
        """
        self._response_event.clear()
        self._response_value = None
        if prompt_callback:
            prompt_callback("prompt", json.dumps({
                "question": question,
                "options": options,
            }))
        # Block until user responds (timeout after 5 minutes)
        self._response_event.wait(timeout=300)
        return self._response_value or options[0]  # default to first option

    def respond(self, value: str):
        """Called from the web layer when the user answers."""
        self._response_value = value
        self._response_event.set()


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


def _normalize_rest_directory(url: str) -> str:
    """
    Given a URL that may point to a specific service (e.g.
    .../rest/services/Addressing/FeatureServer), traverse up to the
    root services directory (.../rest/services).
    """
    idx = url.lower().find("/rest/services")
    if idx == -1:
        return url
    return url[: idx + len("/rest/services")]


def expand_single_service_urls(found_urls: set[str]) -> set[str]:
    """
    If a discovered URL points to a single FeatureServer/MapServer (e.g.
    .../rest/services/Addressing/FeatureServer), traverse up to the root
    services directory so we enumerate all services, not just one.
    """
    expanded: set[str] = set()
    for url in found_urls:
        root = _normalize_rest_directory(url)
        expanded.add(root)
        if root != url:
            progress.log(f"  Expanded single service URL to directory root: {root}")
    return expanded


def crawl_for_arcgis(start_url: str, interaction: InteractionRequest = None) -> set[str]:
    """
    Multi-step crawl using terms from docs/arcgis_rest_crawler_guide.md:
      1. Scrape the start URL for ArcGIS links or GIS-related pages.
      2. Follow only links matching allowed terms (not exclusion terms).
      3. Collect all ArcGIS REST Services Directory root URLs found.
      4. If max depth exhausted with no results, prompt user for next step.
    """
    # Load crawl configuration from the guide file
    guide = load_crawler_guide()
    crawl_keywords = list(set(GIS_LINK_KEYWORDS + guide["allowed_terms"]))
    exclusion_terms = guide["exclusion_terms"]
    max_depth = guide["max_depth"]
    max_pages = guide["max_pages"]

    progress.log(f"Loaded crawler guide: {len(guide['allowed_terms'])} allowed terms, "
                 f"{len(exclusion_terms)} exclusion terms, "
                 f"max depth {max_depth}, max pages {max_pages}")

    progress.log(f"Starting crawl at {start_url}")
    visited: set[str] = set()
    to_visit: list[tuple[str, int]] = [(start_url, 0)]
    found_rest_urls: set[str] = set()
    base_domain = urlparse(start_url).netloc
    pages_crawled = 0
    max_depth_reached = False

    while to_visit and pages_crawled < max_pages:
        url, depth = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)
        pages_crawled += 1

        progress.log(f"  Crawling (depth {depth}/{max_depth}): {url[:80]}{'…' if len(url) > 80 else ''}")

        resp = fetch(url)
        if resp is None:
            progress.log(f"    ✗ Could not reach page")
            continue

        text = resp.text

        # Check for ArcGIS REST URLs in the page body
        rest_urls = extract_arcgis_rest_urls(text)
        if rest_urls:
            progress.log(f"    ✓ Found ArcGIS REST endpoint(s) on this page")
            found_rest_urls.update(rest_urls)

        # If we haven't gone too deep, follow relevant links
        if depth < max_depth:
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

                # Follow links that look relevant (same domain or arcgis.com)
                parsed = urlparse(full_url)
                is_same_domain = parsed.netloc == base_domain
                is_arcgis = "arcgis.com" in parsed.netloc

                if is_same_domain or is_arcgis:
                    href_lower = full_url.lower() + " " + link_text
                    # Skip links matching exclusion terms
                    if exclusion_terms and any(ex in href_lower for ex in exclusion_terms):
                        continue
                    if any(kw in href_lower for kw in crawl_keywords):
                        if full_url not in visited:
                            to_visit.append((full_url, depth + 1))
        else:
            max_depth_reached = True

    progress.stat("Pages crawled", pages_crawled)
    progress.stat("ArcGIS REST endpoints found", len(found_rest_urls))

    # If we exhausted max depth with no results, prompt the user
    if not found_rest_urls and max_depth_reached and interaction:
        progress.log(f"Crawl reached maximum depth ({max_depth} levels) without finding ArcGIS REST endpoints.")
        choice = interaction.ask(
            progress._callback,
            f"The crawl reached {max_depth} levels deep without finding ArcGIS REST endpoints. What would you like to do?",
            [
                "Try common URL patterns (auto-guess)",
                "Enter a different URL",
                "Stop scan",
            ],
        )
        if choice == "Stop scan":
            progress.log("User chose to stop the scan.")
            return expand_single_service_urls(found_rest_urls)
        elif choice == "Enter a different URL":
            progress.log("User chose to enter a different URL. Waiting for input…")
            new_url = interaction.ask(
                progress._callback,
                "Enter a new URL to try (e.g. the ArcGIS REST services directory URL):",
                [],  # free-text input
            )
            if new_url and new_url.strip():
                new_url = new_url.strip()
                progress.log(f"Trying user-provided URL: {new_url}")
                rest_in_url = extract_arcgis_rest_urls(new_url)
                if rest_in_url:
                    found_rest_urls.update(rest_in_url)
                else:
                    # Treat the whole URL as a potential REST directory
                    found_rest_urls.add(new_url)
            return expand_single_service_urls(found_rest_urls)
        else:
            # Default: try guessing
            progress.log("Trying common ArcGIS URL patterns…")
            found_rest_urls = guess_arcgis_urls(start_url)
            return expand_single_service_urls(found_rest_urls)

    if not found_rest_urls:
        progress.log("No ArcGIS REST endpoints discovered via crawl – trying common URL patterns")
        found_rest_urls = guess_arcgis_urls(start_url)

    # Expand any single-service URLs to the full directory root
    found_rest_urls = expand_single_service_urls(found_rest_urls)

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
# Step 1B – LLM web search for ArcGIS REST endpoints
# ---------------------------------------------------------------------------

# Claude API configuration (reads from environment)
_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_LLM_MODEL = os.environ.get("ARCGIS_SCANNER_MODEL", "claude-sonnet-4-6")

_LLM_SEARCH_SYSTEM_PROMPT = """\
You are a web search agent. Your sole task is to find the ArcGIS REST Services \
Directory URL for a specific local government jurisdiction.

## What You Are Looking For

You are searching for a URL that contains one of these target patterns:
- /arcgis/rest/services
- /ArcGIS/rest/services
- /server/rest/services
- rest/services

These are typically hosted at subdomains like:
- https://gis.<domain>/arcgis/rest/services
- https://maps.<domain>/arcgis/rest/services
- https://mapping.<domain>/arcgis/rest/services
- https://gisweb.<domain>/arcgis/rest/services
- https://services.<domain>/arcgis/rest/services
- https://arcgis.<domain>/arcgis/rest/services
- https://webgis.<domain>/arcgis/rest/services
- https://egis.<domain>/arcgis/rest/services
- https://geoportal.<domain>/arcgis/rest/services
- https://opendata.<domain>/arcgis/rest/services
- https://<jurisdiction>.maps.arcgis.com
- https://<jurisdiction>.hub.arcgis.com

Secondary signals (promising but not sufficient alone):
- arcgis.com/home, /arcgis/home, /portal/home
- hub.arcgis.com, opendata.arcgis.com
- /apps/webappviewer, /apps/mapviewer
- "Powered by Esri", "Built with ArcGIS"
- MapServer, FeatureServer, ImageServer, GeocodeServer, GPServer

## Instructions

1. Search the web for the jurisdiction's ArcGIS REST Services Directory.
2. Try multiple search queries if the first doesn't find it (e.g., include "GIS", \
"ArcGIS", "rest services", "map services", the jurisdiction name).
3. Examine search results for URLs matching the target patterns above.
4. If you find a matching URL, verify it by fetching the page if possible.
5. Report ALL matching ArcGIS REST Services Directory URLs you find.

## Output Format

After your search, respond with ONLY a JSON object (no markdown fences):
{
  "found": true or false,
  "urls": ["https://gis.example.gov/arcgis/rest/services", ...],
  "confidence": "confirmed" or "probable" or "not_found",
  "notes": "Brief explanation of what you found"
}

If you find NO matching URLs, set "found" to false and "urls" to an empty list.
Do NOT fabricate or guess URLs. Only report URLs you actually found in search results."""


def llm_search_for_arcgis(jurisdiction_name: str, homepage_url: str = "",
                          interaction: InteractionRequest = None) -> set[str]:
    """
    Use Claude API with web search to find ArcGIS REST Services Directory
    URLs for a government jurisdiction.

    Falls back to the mechanical crawler if no API key is configured.
    """
    if not _ANTHROPIC_API_KEY:
        progress.log("No ANTHROPIC_API_KEY set — falling back to mechanical crawler")
        return crawl_for_arcgis(homepage_url or f"https://www.{jurisdiction_name}.gov",
                                interaction=interaction)

    try:
        import anthropic
    except ImportError:
        progress.log("anthropic package not installed — falling back to mechanical crawler")
        return crawl_for_arcgis(homepage_url or f"https://www.{jurisdiction_name}.gov",
                                interaction=interaction)

    # Step 1: Fast-path probe common subdomains first (free, no LLM needed)
    if homepage_url:
        progress.log("Fast-path: probing common ArcGIS subdomains…")
        fast_results = guess_arcgis_urls(homepage_url)
        if fast_results:
            progress.log(f"Fast-path found {len(fast_results)} endpoint(s) — skipping LLM search")
            return expand_single_service_urls(fast_results)

    # Step 2: LLM web search
    progress.log(f"Searching the web for ArcGIS REST services: {jurisdiction_name}")

    # Build the search prompt
    domain_hint = ""
    if homepage_url:
        parsed = urlparse(homepage_url)
        domain_hint = f"\nTheir website domain is: {parsed.netloc}"

    user_prompt = (
        f"Find the ArcGIS REST Services Directory for: {jurisdiction_name}\n"
        f"{domain_hint}\n\n"
        f"Search for this jurisdiction's GIS/mapping services and locate their "
        f"ArcGIS REST Services Directory URL (contains '/arcgis/rest/services' "
        f"or similar pattern)."
    )

    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": user_prompt}]

    found_urls: set[str] = set()
    max_continuations = 5

    try:
        for continuation in range(max_continuations + 1):
            progress.log(f"  LLM search call {continuation + 1}…")

            response = client.messages.create(
                model=_LLM_MODEL,
                max_tokens=4096,
                system=_LLM_SEARCH_SYSTEM_PROMPT,
                tools=[
                    {"type": "web_search_20250305", "name": "web_search"},
                ],
                messages=messages,
            )

            # If Claude is done, extract the final answer
            if response.stop_reason == "end_turn":
                _parse_llm_search_response(response, found_urls)
                break

            # If Claude needs to continue (server tool hit iteration limit)
            if response.stop_reason == "pause_turn":
                messages = [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": response.content},
                ]
                continue

            # Unexpected stop reason
            progress.log(f"  Unexpected stop_reason: {response.stop_reason}")
            _parse_llm_search_response(response, found_urls)
            break

    except Exception as e:
        progress.log(f"  LLM search error: {e}")
        if homepage_url:
            progress.log("  Falling back to mechanical crawler…")
            return crawl_for_arcgis(homepage_url, interaction=interaction)

    if found_urls:
        progress.log(f"LLM search found {len(found_urls)} ArcGIS REST endpoint(s)")
        for url in found_urls:
            progress.log(f"  ✓ {url}")
    else:
        progress.log("LLM search did not find any ArcGIS REST endpoints")
        # Fall back to mechanical crawler if we have a homepage URL
        if homepage_url:
            progress.log("Falling back to mechanical crawler…")
            return crawl_for_arcgis(homepage_url, interaction=interaction)

    return expand_single_service_urls(found_urls)


def _parse_llm_search_response(response, found_urls: set[str]):
    """Extract ArcGIS REST URLs from the LLM's JSON response."""
    for block in response.content:
        if getattr(block, "type", None) != "text":
            continue
        text = block.text.strip()

        # Try to parse as JSON
        try:
            data = json.loads(text)
            urls = data.get("urls", [])
            for url in urls:
                if isinstance(url, str) and url.startswith("http"):
                    found_urls.add(url.rstrip("/"))
            if data.get("notes"):
                progress.log(f"  LLM notes: {data['notes']}")
            return
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: scan the text for ArcGIS REST URL patterns
        rest_urls = extract_arcgis_rest_urls(text)
        if rest_urls:
            found_urls.update(rest_urls)


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

def is_excluded_by_pattern(layer_name: str) -> bool:
    """Check raster/imagery exclusion patterns."""
    for pat in EXCLUDE_PATTERNS:
        if pat.search(layer_name):
            return True
    return False


def score_service_path(service_name: str) -> int:
    """
    Tier 1 scoring: score based on service/folder path tokens.
    +5 for department identifiers, +4 for land use tokens, +3 for development tokens.
    -5 for exclusion service tokens.
    """
    sn = service_name.lower().replace("/", " ").replace("_", " ").replace("-", " ")
    sn_raw = service_name.lower()
    score = 0

    # Check exclusion service tokens first
    for token in EXCLUDE_SERVICE_TOKENS:
        if token in sn_raw:
            score -= 5
            return score  # strong negative, bail early

    # Department identifiers (+5)
    for token in TIER1_DEPARTMENT_TOKENS:
        if token in sn_raw:
            score = max(score, 5)
            break

    # Land use / zoning tokens (+4)
    if score < 4:
        for token in TIER1_LANDUSE_TOKENS:
            if token in sn_raw:
                score = max(score, 4)
                break

    # Development tokens (+3)
    if score < 3:
        for token in TIER1_DEVELOPMENT_TOKENS:
            if token in sn_raw:
                score = max(score, 3)
                break

    return score


def _count_cluster_hits(text: str, cluster: list[str]) -> int:
    """Count how many keywords from a cluster match in the text."""
    text_lower = text.lower()
    return sum(1 for kw in cluster if kw in text_lower)


def score_layer_name(layer_name: str) -> int:
    """
    Tier 2 scoring: score based on layer name keyword clusters.
    +3 for 3+ keywords from a single cluster, +2 for 1-2 keywords from A-F,
    +1 for administrative geography (Cluster G).
    Negative for exclusion keywords.
    """
    ln = layer_name.lower()

    # Check exclusion keywords
    for kw in EXCLUDE_LAYER_KEYWORDS:
        if kw in ln:
            # Check if it's a standalone match (not nested in a planning term)
            # e.g. "parks" standalone vs "parks master plan"
            has_planning_context = any(pk in ln for pk in [
                "plan", "zone", "zoning", "land use", "overlay", "district",
                "parcel", "subdivision", "historic",
            ])
            if not has_planning_context:
                return -4  # strong negative

    score = 0

    # Score each cluster
    clusters_af = [
        (CLUSTER_A, "A"), (CLUSTER_B, "B"), (CLUSTER_C, "C"),
        (CLUSTER_D, "D"), (CLUSTER_E, "E"), (CLUSTER_F, "F"),
    ]
    max_hits = 0
    total_hits_af = 0
    for cluster, name in clusters_af:
        hits = _count_cluster_hits(ln, cluster)
        max_hits = max(max_hits, hits)
        total_hits_af += hits

    if max_hits >= 3:
        score = max(score, 3)
    elif total_hits_af >= 1:
        score = max(score, 2)

    # Cluster G (administrative geography) — lower confidence
    g_hits = _count_cluster_hits(ln, CLUSTER_G)
    if g_hits > 0 and score == 0:
        score = 1

    # Cluster H (regulatory use restrictions) — moderate confidence
    h_hits = _count_cluster_hits(ln, CLUSTER_H)
    if h_hits > 0:
        score = max(score, 2)

    # Cluster I (hazards and development restrictions) — standalone +2
    i_hits = _count_cluster_hits(ln, CLUSTER_I)
    if i_hits > 0:
        score = max(score, 2)

    # Cluster J (landmarks and civic features) — supporting only, +1
    j_hits = _count_cluster_hits(ln, CLUSTER_J)
    if j_hits > 0 and score == 0:
        score = 1

    return score


def compute_confidence_score(layer: dict) -> int:
    """
    Full confidence score for a layer combining Tier 1 and Tier 2 signals.
    Score >= 4: high confidence, include
    Score 2-3: moderate confidence, include
    Score 0-1: ambiguous
    Score <= -1: exclude
    """
    svc_score = score_service_path(layer["service_name"])
    lyr_score = score_layer_name(layer["layer_name"])
    return svc_score + lyr_score


def filter_layers(layers: list[dict]) -> list[dict]:
    """
    Filter layers using the 3-tier confidence scoring model.
    Includes layers with score >= 2, excludes rasters and low-confidence layers.
    """
    progress.log("Filtering layers using confidence scoring model…")

    scored_layers = []
    excluded_count = 0
    ambiguous_count = 0

    for lyr in layers:
        # Raster/imagery exclusion
        if is_excluded_by_pattern(lyr["layer_name"]):
            excluded_count += 1
            continue

        score = compute_confidence_score(lyr)
        lyr["confidence_score"] = score

        if score >= 4:
            lyr["priority"] = 1  # high confidence
            scored_layers.append(lyr)
        elif score >= 2:
            lyr["priority"] = 2  # moderate confidence
            scored_layers.append(lyr)
        elif score >= 0:
            ambiguous_count += 1
            # Ambiguous — only include if in a planning-named service
            if score_service_path(lyr["service_name"]) >= 3:
                lyr["priority"] = 3
                scored_layers.append(lyr)
        else:
            excluded_count += 1

    # Sort by priority then score descending
    scored_layers.sort(key=lambda x: (x.get("priority", 99),
                                       -x.get("confidence_score", 0)))

    high = sum(1 for l in scored_layers if l.get("priority") == 1)
    moderate = sum(1 for l in scored_layers if l.get("priority") == 2)
    low = sum(1 for l in scored_layers if l.get("priority") == 3)

    progress.log(f"  {high} high-confidence, {moderate} moderate-confidence, "
                 f"{low} context-included layers")
    progress.log(f"  {excluded_count} excluded, {ambiguous_count} ambiguous")
    progress.stat("Layers after keyword filter", len(scored_layers))
    return scored_layers


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

def scan(website_url: str, output_dir: str = ".", progress_callback=None,
         mode: str = "homepage", interaction: InteractionRequest = None,
         jurisdiction_name: str = "") -> dict:
    """
    Full pipeline: validate → search/crawl → enumerate → filter → deduplicate → export.

    Args:
        website_url: Root URL of the government website (or REST directory / GIS page).
        output_dir: Directory for output files.
        progress_callback: Optional callable(event_type, message) for live updates.
        mode: Workflow mode selected by user:
            "direct"   – URL is an ArcGIS REST Services Directory root (Path A).
            "homepage" – URL is the jurisdiction's main website (Path B).
            "gis_page" – URL is a GIS department / resources page (Path B).
        interaction: Optional InteractionRequest for mid-scan user prompts.
        jurisdiction_name: Optional human-readable name (e.g., "City of Las Vegas").
            If empty, derived from the URL domain.

    Returns:
        dict with keys: xl_path, md_path, stats, error (if any).
    """
    progress.reset(callback=progress_callback)

    # Re-read the planning layer pattern skill document from the repo
    # so any updates to the keywords are picked up without restarting
    reload_keywords_from_skill_doc()

    print("\n" + "=" * 60)
    print("  Government ArcGIS Feature Layer Scanner")
    print("=" * 60 + "\n")

    # Step 0 – Validate URL
    progress.log(f"Validating URL: {website_url}")
    validation = validate_url(website_url, mode=mode)
    if validation["valid"]:
        progress.log(f"✓ URL is valid and reachable — {validation['message']}")
    else:
        progress.log(f"✗ URL validation failed — {validation['message']}")
        if progress_callback:
            progress_callback("error_msg", f"URL validation failed: {validation['message']}")
        progress.summary()
        return {"error": f"URL validation failed: {validation['message']}",
                "stats": dict(progress.stats)}

    # Step 1 – find ArcGIS REST endpoints (skipped for "direct" mode)
    if mode == "direct":
        # Path A: user provided the REST Services Directory URL directly
        rest_url = website_url.rstrip("/")
        # Normalise to the root services directory
        idx = rest_url.lower().find("/rest/services")
        if idx != -1:
            rest_url = rest_url[: idx + len("/rest/services")]
        rest_urls = {rest_url}
        progress.log(f"Direct mode: using ArcGIS REST directory at {rest_url}")
    else:
        # Path B: search for ArcGIS REST endpoints via LLM web search
        if not jurisdiction_name:
            # Derive a human-readable name from the domain
            parsed_url = urlparse(website_url)
            domain = parsed_url.netloc.replace("www.", "")
            # e.g., "cityoflasvegas.com" → "cityoflasvegas" → "city of las vegas"
            jurisdiction_slug = domain.split(".")[0]
            # Insert spaces before capital letters and replace common separators
            jurisdiction_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", jurisdiction_slug)
            jurisdiction_name = jurisdiction_name.replace("-", " ").replace("_", " ")

        label = "GIS department page" if mode == "gis_page" else "jurisdiction homepage"
        progress.log(f"Search mode: finding ArcGIS endpoints for {jurisdiction_name} ({label})")
        rest_urls = llm_search_for_arcgis(
            jurisdiction_name=jurisdiction_name,
            homepage_url=website_url,
            interaction=interaction,
        )

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
