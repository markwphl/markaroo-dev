# ArcGIS REST Services Discovery: Jurisdiction Web Crawler Guide

## Purpose

This document instructs an LLM agent or Python-based web crawler on how to navigate a municipal or county government jurisdiction's homepage to locate its **ArcGIS REST Services Directory**. The crawler follows a targeted, selective path — it does not perform a full-site crawl. It only follows links whose **page title** or **URL path segments** match a configurable set of terms defined in this guide.

The ArcGIS REST Services Directory is typically found at a URL ending in:
```
/arcgis/rest/services
```
or hosted on a subdomain such as:
```
https://gis.<jurisdiction>.gov/arcgis/rest/services
https://maps.<jurisdiction>.gov/arcgis/rest/services
```

> **Scope Restriction:** The crawler is intentionally limited to planning, zoning, development, GIS/maps, property/assessor, open data, and government navigation pages. It does **not** follow links related to engineering, environmental review, transportation, public works, code enforcement, or other municipal departments outside this scope. This is by design. Do not expand the Allowed Terms Lists beyond this domain boundary without explicit review. The goal is precision, not breadth.

---

## Crawler Behavior Contract

The crawler must obey the following rules at every hop:

1. Start at the jurisdiction's **root homepage URL** (e.g., `https://www.cityofexample.gov`).
2. At each page, extract all `<a href>` links visible in the page body and navigation.
3. For each link, evaluate **both** the link's display text/title **and** its URL path against the **Allowed Terms Lists** below.
4. Follow **only** links that match at least one term from any active category in the Allowed Terms Lists.
5. Do **not** follow links that match terms in the **Exclusion List**.
6. At each followed page, scan the full page text and all links for patterns matching the **ArcGIS Target Patterns** list.
7. If a target pattern is found, record and return the URL. Crawl complete.
8. If no target is found, continue recursively from that page, applying the same rules.
9. Stop and report failure if **Max Depth** is exceeded without finding a target.

---

## Configuration Block

> **Instructions for maintainers:** All terms are stored in categorized lists below. To add, remove, or disable a category, edit the relevant section. Each category has an `ENABLED` flag. Set to `false` to deactivate an entire category without deleting its terms.

---

## Allowed Terms Lists

Match is **case-insensitive**. Partial matches on URL path segments and link text are permitted (e.g., `planning` matches `planning-and-zoning` and `communityplanning`).

---

### CATEGORY: Planning & Zoning
**ENABLED:** `true`

```
Planning
Zoning
Land Use
Zoning Map
PlanningMap
ZoningMap
Planning Commission
Planning Board
Comprehensive Plan
Master Plan
Long Range Planning
Current Planning
Development Review
Site Plan
Subdivision
Variance
Board of Zoning Appeals
ZBA
Overlay District
Rezoning
Land Development
Entitlement
```

---

### CATEGORY: Development & Permitting
**ENABLED:** `true`

```
Development
Community Development
Building
Building Department
Building Permits
Permits
Building Inspection
Code Compliance
Inspection
Land Development Code
Development Services
Development Review
ePermit
Online Permits
Permit Portal
Construction
Grading
Site Development
```

---

### CATEGORY: GIS, Maps & Spatial Data
**ENABLED:** `true`

```
GIS
Geographic Information Systems
Geography
Geospatial
Maps
Map Viewer
Web Map
CityMap
CityView
CountyMap
CountyView
iMap
WebGIS
eGIS
GeoHub
Geoportal
Interactive Map
Parcel Map
Tax Map
Aerial
Imagery
Basemap
Address Map
Map Gallery
Map Services
MapServer
FeatureServer
ImageServer
GeocodeServer
REST
REST Services
ArcGIS
Esri
ArcGIS Online
AGOL
ArcGIS Hub
Feature Service
Services Directory
```

---

### CATEGORY: Open Data & Data Portals
**ENABLED:** `true`

```
Open Data
Data Portal
Data Download
Geospatial Data
Public Data
Data Catalog
Datasets
GIS Data
Hub
Open Government
Transparency
```

---

### CATEGORY: Assessor & Property Records
**ENABLED:** `true`

```
Assessor
Assessments
Property
Property Search
Property Records
Parcel
Parcel Viewer
Parcel Search
Tax Records
Tax Map
Land Records
Real Property
Real Estate
Property Information
CAMA
Assessment Map
```

---

### CATEGORY: Government Navigation Hubs
**ENABLED:** `true`

```
Departments
Services
Online Services
Government
City Hall
County Administration
Resources
Tools
Portal
```

---

## Exclusion List

Do **not** follow links that match any of these terms, even if they also match an allowed term. These are noise or dead-ends for ArcGIS discovery.

**ENABLED:** `true`

```
News
Press Release
Calendar
Events
Agenda
Minutes
Meeting
Job
Employment
Career
HR
Human Resources
Budget
Finance
Purchasing
Bid
RFP
Vendor
Parks
Recreation
Library
Museum
Animal
Police
Fire
Emergency
911
Trash
Recycling
Utility Billing
Utilities Payment
Payment
Pay Online
Login
Register
Subscribe
Social Media
Facebook
Twitter
LinkedIn
Instagram
YouTube
Contact Us
About Us
Accessibility
Privacy Policy
Terms of Use
Sitemap
```

---

## ArcGIS Target Patterns

The crawler declares success when any of the following patterns are found in a **page URL**, **page title**, **page body text**, or **any link href** on a visited page.

```
/arcgis/rest/services
/ArcGIS/rest/services
arcgis/rest/services
rest/services
/server/rest/services
MapServer
FeatureServer
ImageServer
GeocodeServer
GPServer
services/rest
```

**Secondary signals** (not a success condition alone, but increase confidence you are on the right path):

```
arcgis.com/home
/arcgis/home
/portal/home
hub.arcgis.com
opendata.arcgis.com
<subdomain>.maps.arcgis.com
/apps/webappviewer
/apps/mapviewer
/apps/instant
Powered by Esri
Built with ArcGIS
```

---

## Common URL Subdomain Patterns

Before crawling internal links, the crawler **should also probe** these common ArcGIS hosting subdomains directly as a fast-path check:

```
https://gis.<domain>/arcgis/rest/services
https://maps.<domain>/arcgis/rest/services
https://mapping.<domain>/arcgis/rest/services
https://gisweb.<domain>/arcgis/rest/services
https://services.<domain>/arcgis/rest/services
https://arcgis.<domain>/arcgis/rest/services
https://webgis.<domain>/arcgis/rest/services
https://egis.<domain>/arcgis/rest/services
https://geoportal.<domain>/arcgis/rest/services
https://opendata.<domain>/arcgis/rest/services
https://<jurisdiction>.maps.arcgis.com
https://<jurisdiction>.hub.arcgis.com
https://<jurisdiction>gis.opendata.arcgis.com
```

> Replace `<domain>` with the root domain of the jurisdiction (e.g., `cityofexample.gov`) and `<jurisdiction>` with the short name (e.g., `examplecity`).

---

## Crawl Parameters

| Parameter | Default Value | Description |
|---|---|---|
| `MAX_DEPTH` | `5` | Maximum number of hops from the homepage before declaring failure |
| `MAX_PAGES_PER_DOMAIN` | `75` | Maximum total pages visited before stopping |
| `REQUEST_DELAY_SECONDS` | `1.5` | Polite delay between requests |
| `FOLLOW_EXTERNAL_LINKS` | `false` | Whether to follow links to external domains |
| `USER_AGENT` | `ArcGIS-Discovery-Bot/1.0` | HTTP User-Agent header string |
| `TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `RESPECT_ROBOTS_TXT` | `true` | Whether to honor robots.txt exclusions |
| `FAST_PATH_PROBE_ENABLED` | `true` | Probe common subdomains before crawling |

---

## Crawl Decision Pseudocode

```
function should_follow(link_text, link_url):
    if matches_any(link_url + link_text, EXCLUSION_LIST):
        return False
    for category in ALLOWED_TERMS_LISTS:
        if category.ENABLED:
            if matches_any(link_url + link_text, category.terms):
                return True
    return False

function is_target(url, page_title, page_body, all_links):
    for pattern in ARCGIS_TARGET_PATTERNS:
        if pattern in url: return True
        if pattern in page_body: return True
        for link in all_links:
            if pattern in link.href: return True
    return False
```

---

## LLM Prompt Template

Use this prompt to instruct an LLM agent performing the crawl:

```
You are a web navigation agent. Your goal is to find the ArcGIS REST Services Directory 
for the jurisdiction at: {{HOMEPAGE_URL}}

Rules:
1. Start at the homepage. Fetch and parse all visible navigation links.
2. Only follow links whose display text or URL contains terms from the Allowed Terms Lists 
   in your instructions. Do not follow links in the Exclusion List.
3. At each page, scan all URLs and page content for the pattern: /arcgis/rest/services
4. If found, return the full URL immediately.
5. If not found, continue following matching links up to {{MAX_DEPTH}} hops deep.
6. Before crawling internal links, also probe these fast-path subdomains:
   {{FAST_PATH_SUBDOMAIN_LIST}}
7. Report the final ArcGIS REST URL if found, or list the closest matching pages if not found.
8. Do not fetch more than {{MAX_PAGES_PER_DOMAIN}} pages total.
```

---

## Output Schema

The crawler should return a structured result in the following format:

```json
{
  "jurisdiction": "City of Example",
  "homepage_url": "https://www.cityofexample.gov",
  "arcgis_rest_url": "https://gis.cityofexample.gov/arcgis/rest/services",
  "discovery_method": "fast_path_probe | link_crawl",
  "hops": 2,
  "pages_visited": 5,
  "confidence": "confirmed | probable | not_found",
  "path_taken": [
    "https://www.cityofexample.gov",
    "https://www.cityofexample.gov/departments/gis",
    "https://gis.cityofexample.gov/arcgis/rest/services"
  ],
  "notes": "Optional: secondary signals observed or error conditions"
}
```

---

## Maintenance Log

| Date | Version | Change Description | Author |
|---|---|---|---|
| 2026-03-14 | 1.0 | Initial release | — |
| 2026-03-14 | 1.1 | Removed: Code Enforcement, Engineering, Hearing Examiner, Board of Appeals, Environmental category, Transportation & Public Works category, SEPA, Shapefiles. Added scope restriction notice to Purpose section. | — |

---

## Version

`1.1` — March 2026

To update allowed terms, exclusions, or crawl parameters, edit the relevant sections above and increment the version number in the Maintenance Log.
