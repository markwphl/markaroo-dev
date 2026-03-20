# Planning Department GIS Layer Pattern Analysis
**Source:** 300+ ArcGIS REST service layers across 7+ municipal/county GIS environments  
**Version:** 3.0 — Complete rebuild of v2.2. Key changes: enforced service-domain exclusion logic (exclude the service, not the layer name); new hard-exclusion pattern list for platform-internal and administrative layers; added GeneralPlan as Tier 1 token; expanded cluster keywords; strengthened single-service MapServer traversal rule; clarified Cluster J standalone scoring enforcement.  
**Purpose:** Equip an LLM and a Python web crawler with structured rules to identify layers associated with Planning Departments, Planning Commissions, and Community Development Departments in local government ArcGIS REST environments.

---

## 0. Critical Design Principles

Read these before applying any rule.

**Principle 1 — Exclude the service, not the layer name.**  
A layer called `Fire Districts` in a `/CDD/` or `/Planning/` service is a planning boundary layer and should be included. The same name in a `/Fire_/` or `/FD_/` service is operational and should be excluded. Exclusion logic applies first to the service path, and only secondarily to the layer name. Do not exclude a layer solely because its name references a non-planning topic when it lives in a confirmed planning service.

**Principle 2 — False positives from confirmed planning services are acceptable.**  
When a service folder is confirmed as planning (CDD, EnerGov, ComDev, Planning, GeneralPlan), include all layers except those matching the Hard Exclusion Patterns in Section 4.10. Do not apply Tier 2 scoring to thin out confirmed-service layers — scoring is for disambiguation, not for confirmed-service filtering.

**Principle 3 — Traverse all layers in a single-service MapServer.**  
When a county or municipality publishes a single all-purpose MapServer with a generic service name, the tool must enumerate every layer in that service and score each individually. Do not skip the service because the name is generic. Generic service names are normal and expected in jurisdictions under 150k population.

**Principle 4 — Hard Exclusion Patterns override all other rules.**  
Layers matching Section 4.10 patterns are excluded regardless of service path, score, or context. No exceptions.

---

## 1. How to Use This Guide

This document defines a three-tier classification system. Apply markers in order of precedence:

1. **Service Path Signals (Tier 1)** — strongest indicator; comes directly from how the GIS admin named the service folder
2. **Layer Name Keyword Signals (Tier 2)** — second strongest; reflects the content domain
3. **Exclusion Signals** — used to suppress false positives

A layer qualifies as a **Planning department layer** when it satisfies one or more Tier 1 signals, OR two or more Tier 2 signals, AND does not trigger an Exclusion signal.

### Structural Patterns — Apply Before Scoring

**Single-service county MapServers (most critical pattern):**  
Smaller counties and municipalities (population < 150k) commonly publish a single all-purpose MapServer with a generic service name such as `Website_Map_CityView`, `Website_Map`, `County_Parcels`, `PublicMap`, `PropertySearch`, `ParcelViewer`, `CityView`, or similar. These services contain all GIS layers for the entire jurisdiction — zoning, parcels, flood, historic, administrative boundaries — in a single flat list.

**Crawler instruction:** When you encounter a MapServer with a generic service name AND any layer within it scores ≥ 1 on any Tier 2 cluster, treat the entire service as a planning candidate and enumerate ALL layers. Apply Tier 2 scoring to each layer individually. Do not skip this service because the name is generic. The generic name IS the expected pattern, not an anomaly.

**Priority service for traversal:** When a Surry-pattern REST directory lists multiple services (e.g., `Parcels`, `basemap`, `ForeclosureMap`, `Website_Map_CityView`, `InternalUse`), prefer the largest public-facing MapServer (highest layer count, no `InternalUse` or `ForeclosureMap` in the name) as the primary traversal target.

**ArcGIS Online (AGOL) flat FeatureServer lists:**  
AGOL orgs present 50–300 individually-named FeatureServer services with no folder hierarchy. Each service name IS effectively the layer name for Tier 1 matching purposes. Apply Tier 1 token matching directly against the service name string. Tier 2 cluster matching applies normally. Do not require a folder-level signal before applying Tier 2 rules.

**Folder-organized on-premises servers:**  
When the REST directory uses `[ServiceGroup]/[ServiceName]` two-level naming, the ServiceGroup is the strongest Tier 1 signal. A CDD, Planning, ComDev, EnerGov, or GeneralPlan folder elevates all child services to high confidence, subject only to Section 4.10 hard exclusions.

---

## 2. Tier 1 — URL Service Path Signals (Highest Confidence)

These strings appear in the `/services/` segment of the ArcGIS REST endpoint URL. When present, they are near-definitive evidence of a Planning or Community Development service.

### Explicit Department Identifiers

| Token | Example URL Fragment | Notes |
|-------|---------------------|-------|
| `ComDev` | `/services/ComDev/FeatureServer/` | Community Development — canonical abbreviation; West/Southwest |
| `CDD` | `/services/CDD/HousingElement/MapServer/` | Community Development Department — California |
| `Planning` | `/services/Planning/Zoning/MapServer/` | Direct department name as folder |
| `GeneralPlan` | `/services/GeneralPlan/MapServer/` | General Plan document service — California/Southwest |
| `General_Plan` | `/services/General_Plan/MapServer/` | Same with underscore |
| `LandDev` | `/services/LandDev/Subdivisions/MapServer/` | Land Development folder; Southeast |
| `CommunityDevelopment` | `/services/CommunityDevelopment/FeatureServer/` | Full department name |
| `EnerGov` | `/services/EnerGov/DisplayMap/MapServer/` | Tyler EnerGov permitting/planning platform — always planning-adjacent |
| `PLU` | `/services/CLV_PLU/FeatureServer/` | Planned Land Use |
| `ROIS` | `/services/ROIS/FeatureServer/` | Regional/municipal overlay index system |

### Land Use and Zoning Service Names

| Token / Pattern | Notes |
|----------------|-------|
| `Zoning` / `ZONING` | Any case variant |
| `ZCU` | Zoning Code Update |
| `Land_Use` / `LandUse` / `_LU_` | Standalone or embedded |
| `Future_Land_Use` | General Plan / Comprehensive Plan layer |
| `General_Plan` / `GeneralPlan` | General Plan document layers |
| `Residential_Zoning` | Zoning sub-category |
| `MasterPlan` / `Master_Plan` | Any master plan boundary |
| `Downtown.*Plan` / `DTMasterPlan` | Downtown-specific planning documents |
| `HousingElement` | California statutory General Plan element |
| `Comprehensive_Plan` | Midwest/Southeast equivalent of General Plan |
| `FLUM` | Future Land Use Map |
| `Form.Based.Code` | Form-based zoning regulatory layer |
| `Growth_Framework` | Urban growth policy layer |

### Parcel and Property Services

| Token / Pattern | Notes |
|----------------|-------|
| `Parcels` / `PARCELS` | Base cadastral layer |
| `CC_PARCELS` / `CLV_PARCELS` | Jurisdiction-prefixed parcel services |
| `TIF_Parcels` / `TIF_Zones` | Tax Increment Financing |
| `Assessor.*Parcel` / `PARCELS_SHP` | Assessor parcel geometry |
| `Mello_Roos` / `MelloRoos` / `Mello-Roos` | CFD financing boundary — California |

### Development Activity Services

| Token / Pattern | Notes |
|----------------|-------|
| `Development_Agreement` / `Agreement_Areas` | Binding land development agreements |
| `Subdivision` / `Subdivision_Sections` | Subdivision plat management |
| `Special_Area_Plan` / `Special_Area_Boundaries` | Subarea planning |
| `Specific_Plans` / `SpecificPlans` | California term for special area plans |
| `Precise_Plan` / `PrecisePlan` | California subarea regulatory plan |
| `Opportunity_Sites` | Housing element / redevelopment site inventory |
| `Urban_Growth_Boundary` / `UGB` | Growth boundary service |

### Historic Preservation Services

| Token / Pattern | Notes |
|----------------|-------|
| `Historic_District` | District boundary designation |
| `Historic.*Inventory` | Historic resource survey layer |
| `NRHP_Boundary` | National Register of Historic Places |

---

## 3. Tier 2 — Layer Name Keyword Signals (Medium-High Confidence)

No single term is conclusive alone. Confidence increases with co-occurrence. Three or more terms from the same semantic cluster = high confidence. Apply to all layers in confirmed Tier 1 services without further scoring gating.

### Cluster A: Zoning and Land Use Regulation
`Zoning`, `Zone`, `Zone Overlay`, `Zone Map`, `Overlay`, `Land Use`, `Future Land Use`, `General Plan`, `GP` (abbrev.), `Comprehensive Plan`, `FLUM`, `Planned Development`, `Form-Based Code`, `Infill`, `Residential Zoning`, `UGB`, `Zoning Code Update`, `ZCU`, `Hillside.*Code`, `Hillside.*Regulation`, `Heights` (building height limits), `Tree.*Zone`, `SB 9.*Overlay`, `AB 2923.*Zone`, `Two-Unit.*Overlay`, `Lot Split.*Zone`, `State Density Bonus`, `Ministerial.*Zone`, `ADU.*Overlay`, `ADU.*Zone`, `Accessory Dwelling`, `Junior ADU`, `Combining District`, `Combining_Districts`, `Overlay District`, `Downtown.*Character`, `Downtown.*Plan`

### Cluster B: Development Review and Entitlements
`Subdivision`, `Special Use Permit`, `Development Agreement`, `Agreement Area`, `TDR`, `TIF`, `Annexation`, `Annex`, `Planned Development`, `Planned Unit Development`, `PUD`, `Housing Element`, `Housing Element Sites`, `By-Right`, `Opportunity Sites`, `Project Development`, `Innovation.*Parcel`, `BMR`, `Below Market Rate`, `Low Income Housing`, `Affordable Housing`, `AffordableHousing`, `CFD`, `CFD Parcels`, `Mello-Roos`, `VAD`, `Voluntary Agricultural.*District`, `Voluntary Agricultural.*Parcel`, `RHNA`, `Fire Districts` (when not in Fire service), `Park Areas` (when not in Parks service), `Public Parks` (when not in Parks service), `Neighborhood.*District`, `Community Facilities District`

### Cluster C: Comprehensive / Master Planning
`Master Plan`, `General Plan`, `Comprehensive Plan`, `Future Land Use`, `Growth Framework`, `Special Area Plan`, `Specific Plans`, `Specific Plan Area`, `Precise Plan`, `Civic Master Plan`, `Downtown.*Plan`, `Downtown Specific Plan`, `Downtown.*Boundary`, `Downtown.*Blocks`, `Town Center.*Plan`, `Sphere of Influence`, `Urban Growth Boundary`, `Transit Priority Area`, `High Quality Transit Corridor`, `Corridor Plan`, `Small Area Plan`, `Area Plan`, `Sector Plan`, `Neighborhood Planning Areas`, `Neighborhood Preservation`, `General Plan.*Land Use`, `Horizon.*Land Use`, `Greenline`

### Cluster D: Historic Preservation
`Historic District`, `Historic Sites`, `Historic Buildings`, `Historic Inventory`, `NRHP`, `Landmark`, `Local Historic District`, `National Historic District`, `Heritage District`, `Preservation District`, `Historical Inventory`, `Mount Airy Historic`, `Pilot Mountain Historic`, `Downtown.*Historic`, `Historic.*Overlay`

### Cluster E: Environmental Overlay (Planning-Regulated)
`Stream Margin`, `Wildfire Hazard`, `Wildfire District`, `Wildfire Zone`, `WUI`, `ESA`, `Wetlands`, `Wetland Buffer`, `Riparian Buffer`, `Riparian Zone`, `Watershed` (with overlay/planning context), `Flood Zone`, `Floodplain`, `Floodway`, `Floodways`, `Floodway Channels`, `Floodway Creeks`, `Flood.*Plain`, `FEMA Flood`, `FEMA Floodplain`, `FEMA FIRM`, `100 Year Flood`, `100-Year Flood`, `500 Year Flood`, `500-Year Flood`, `100 Year Floodway`, `Special Flood Hazard Area`, `SFHA`, `Flood Zone Parcels`, `FIRM` (polygon layers — NOT Map Index), `Tree Preservation`, `Agricultural.*Buffer`, `Conservation.*Easement`, `Earthquake Zone`, `Seismic Zone`, `Seismic Hazard`, `Tsunami Zone`, `Liquefaction Zone`, `Steep Slope`, `Slope.*Hazard`, `Landslide.*Zone`, `Geologic Hazard`, `Non Attainment`, `Fire Hazard` (hazard overlay, not operational), `Fire Zone` (zoning overlay)

### Cluster F: Cadastral and Property Reference
`Parcels`, `Assessor Parcels`, `PID`, `TIF Parcels`, `CFD Parcels`, `Flood Zone Parcels`, `Parcel Owner`, `Parcel Report`, `Innovation.*Parcel`, `Parcel Dimensions`, `Building Outlines`, `Address Point`, `Easement` (Conservation or Agricultural type only — see Section 4.10), `Right of Way` (in planning platform context only)

### Cluster G: Administrative Boundaries
`Neighborhoods`, `Neighborhood Boundary`, `Neighborhood Association`, `Neighborhoods of.*`, `City Limits`, `City Boundary`, `Municipal Boundary`, `Municipalities`, `County Boundary`, `Adjacent Counties`, `Council Districts`, `Wards`, `ZIP Codes`, `Zipcodes`, `Zip Code Boundaries`, `Census Tracts` (boundary layer — not census data join), `Voting Districts`, `Election Districts`, `School Districts`, `School Catchment`, `School Attendance Zone`, `School District`, `Elementary School District`, `Middle School District`, `High School District`, `Township`, `ETJ`, `Sphere of Influence`, `Urban Growth Boundary`, `Metro` (transit district boundary), `Public Owned Land`, `Fire Districts` (planning reference — see Principle 1), `Fire Response Districts` (planning reference), `Fire Tax Districts` (planning reference)

### Cluster H: Regulatory Use Restrictions
`Billboard Buffer`, `Outdoor Lighting Code`, `Short Term Rental`, `Prohibited Area`, `Small Cell Wireless`, `Cell Towers`, `Scenic Byway`, `Pedestrian Mall`, `Gaming.*Overlay`, `Community Residence`, `Alcohol.*Buffer`, `Adult.*Use.*Overlay`, `Cannabis.*Overlay`, `Noise.*Contour`, `Master Sign Program`, `Sign.*Program`, `Airport.*Influence`, `Airport.*Compatibility`, `Airport.*Zone` (compatibility overlay — not facility point)

### Cluster I: Hazards and Development Restrictions
`Floodplain`, `Flood Zone`, `Floodway`, `Flood.*Area`, `100 Year Flood`, `500 Year Flood`, `FEMA Flood`, `FEMA Floodplain`, `SFHA`, `FIRM` (not Map Index), `Fire Zone`, `Fire Hazard`, `Wildfire`, `WUI`, `Earthquake Zone`, `Seismic Zone`, `Liquefaction`, `Tsunami Zone`, `Geologic Hazard`, `Steep Slope`, `Landslide`, `Erosion.*Zone`, `Contour` (with development restriction context), `10.*Foot.*Contour`, `100.*Foot.*Contour`, `Topo.*Contour`, `Contours` (5FT, 10FT, 20FT, 100FT variants), `Wetlands`, `Wetland.*Buffer`, `Riparian Buffer`, `Riparian Zone`, `Stream.*Buffer`, `River.*Buffer`, `Rivers`, `Streams`, `Ponds`, `Lakes`, `Waterbodies`, `Watersheds`, `Hydrology`, `Conservation Easement`, `Agricultural District`, `Voluntary Agricultural`, `Farm.*Buffer`, `Voluntary Agricultural Parcels Half Mile Buffer`

### Cluster J: Landmarks and Civic Features (Supporting Only)
**Scoring rule: Cluster J keywords alone are not sufficient for inclusion. Require at least one co-occurring Tier 1 signal or Tier 2 signal from Clusters A–I. Do not include Cluster J layers when they are standalone in a non-planning service.**

`High School`, `Middle School`, `Elementary School`, `Public School`, `School.*Location`, `Parks`, `Park.*Location`, `Civic.*Area`, `City Hall`, `Fire Station` (civic reference — not operational), `Police Station` (civic reference — not operational), `Library`, `Community Center`, `Transit Stop`, `Bus Stop`, `Light Rail Stop`, `Train Station`, `Airport` (compatibility context only), `Rivers`, `Streams`, `Lakes`, `Open Space`, `Greenway`, `Park Facilities`, `VTA.*Station`, `Caltrain.*Station`, `Major.*Transit.*Stop`, `Bus.*Stop` (individual stop points — support only)

---

## 4. Exclusion Signals

### 4.1 — Service-Path Exclusions (Apply First)
When the service path contains these tokens AND the layer is NOT in a co-occurring confirmed planning service, exclude the layer.

| Service Token | Exclude |
|---|---|
| `Fire_`, `FD_`, `EMS_`, `PHANTOMS` | Fire/emergency operational services |
| `PW_`, `DPW_`, `PublicWorks` | Public Works operational services |
| `SCL`, `RTC_` | Transportation/street centerline services |
| `LIVE_CLV_BUS`, `CLV_BUS`, `Business_License` | Business license services |
| `Parks_Protected_Use`, `Pools_View`, `Community_Centers_View` | Parks facility services |
| `Utilities`, `Water_`, `Sewer_`, `Storm_`, `Stormwater_`, `Lucity` | Utility infrastructure services |
| `Police_`, `Mark43_` | Law enforcement services |
| `InternalUse` | Internal-only services — do not traverse for public planning layers |

### 4.2 — Layer Name Exclusions: Public Works / Transportation Infrastructure
Exclude these layer names regardless of service, unless the service is a confirmed planning service (Tier 1 signal present):

`RAILROADS`, `ROAD` (standalone exact match), `ROADS` (standalone exact match), `HWY LABELS`, `STRUCTURES`, `BUILDING FOOTPRINTS` (standalone — not `Building Outlines` in a parcel service), `FIRE HYDRANTS`, `FIRE HYDRANTS AND WATER POINTS`, `FIRE WATER POINTS`, `FIRE WATER POINTS`, `Bike Trails`, `Bicycle Lane`, `Bicycle Route`, `Equestrian Trails`, `Trailheads`, `Bus Stops` (standalone operational — not in planning service), `Pavement Condition`, `Pavement Index`, `Pavement_Index`, `Street Sweeping`, `Guardrails`, `Handicap Ramps`, `Street Lights`, `Traffic Signal`, `Truck Routes`, `Street Centerlines`, `Road Closures`, 'Curbs', 'Caltrans', 'Curblines', 'Stops', 'Traffic Stops', 'Snow*', 'Speed*' , 'Speed Zones', 'Speed Limit*, '*_copy', '* copy'

### 4.3 — Layer Name Exclusions: Fire / Emergency Operational
Exclude when NOT in a confirmed planning service:

`Fire Map`, `Phantoms`, `Emergency`, `EMS`, `Fire Pre Plan`, `Fire Run`, `Fire Stations` (point location — not district boundary), `Fire Incidents`

Note: `Fire Districts`, `Fire Response Districts`, `Fire Tax Districts` are **planning reference boundaries** and are included when not in a Fire service folder. See Cluster B and G.

### 4.4 — Layer Name Exclusions: Business License / Revenue
`Business Licenses`, `Active Business Licenses`, `Gaming Restricted`, `Gaming Non-Restricted`, `Alcohol On-Premise`, `Alcohol Off-Premise`, `Massage Establishment`, `Marijuana Establishments`, `Daily Labor Service`, `Financial Institution`, `Restaurants` (as license record), `Alcohol Beverage Control License`, `Open Air Vending`

### 4.5 — Layer Name Exclusions: Utilities
`Water Hydrant`, `Water Meter`, `Water Service`, `Sewer`, `Sanitary`, `Storm Drain`, `Recycled Water`, `Irrigation Controller`, `Backflow`, `Odor Sample`, `Water Main`, `Sewer Main`, `Stormwater Basin`, `Sanitary Sewer`

### 4.6 — Layer Name Exclusions: Police / Public Safety Operational
`Police Beats`, `Police Traffic Citations`, `Crime`, `Reporting Districts` (police), `Police Incidents`

### 4.7 — Layer Name Exclusions: Parks Operational (when in Parks service)
`Pools`, `Park Lights`, `Park Parking`, `Trail Sign*`, 'Park Points'

Note: `Park Areas`, `Public Parks`, `Park Facilities` are **included** when not in a Parks operational service folder. See Cluster B/J.

### 4.8 — Layer Name Exclusions: Schools Operational
`CCSD Schools`, `Private Schools`, `School Points` (standalone facility point — not district boundary)

Note: School district/catchment/attendance zone boundaries are **included** — see Cluster G.

### 4.9 — Layer Name Exclusions: Basemap / Imagery
`Aerial Imagery`, `Historical Imagery`, `Basemap`, `Ortho`, `Orthophoto`, `Satellite`, `Imagery` , `History Point*`, `HistoryPolygon*`, `Spatial Polyline*`, `SpatialCollectionPolyline*`, `Location` (exact match — generic geometry record), `Converted_Graphics*`, `Feature.MAPREAD.*`, `CityWide.SDE.*`, 'Spatial', 'Spatial_Collection', 'Library Card*', 'Hisory Polygon', 'SpatialCollectionPoint', 'SpatialCollecitonPolygon', 

### 4.10 — Hard Exclusion Patterns (Override All Rules)
These patterns are excluded regardless of service path, Tier 1 boost, or any other signal. No exceptions.

**Annotation and label classes:**
`*anno*`, `annotation_*`, `lot_anno*`, `*_anno_*`, `*Labels*`, `HWY LABELS`, `*label*`

**Platform-internal geometry objects:**
`History Point*`, `HistoryPolygon*`, `Spatial Polyline*`, `SpatialCollectionPolyline*`, `Location` (exact match — generic geometry record), `Converted_Graphics*`, `Feature.MAPREAD.*`, `CityWide.SDE.* ,  'Spatial*', 'Spatial_Collection', 'Library Card*', 'Hisory Polygon', 'SpatialCollectionPoint', 'SpatialCollecitonPolygon'

**Generic/ambiguous layer names:**
`Default` (exact match), `A_*` (annotation class prefix), '*_copy', '* copy'

**Imagery and graphics:**
`*images*`, `*graphics*`, `*imagery*`, `*aerial*`, `*Converted_Graphics*`

**Transit operational layers (standalone — not in planning service):**
`Bus_Routes_and_Stops*`, `BusStops_*` (raw date-stamped transit agency data), `VTA*Stn*`, `*caltrain_stations_project*`, `Lawrence_Station` (transit station point), `*_Station` (transit point — not boundary or planning overlay)

**Street sweeping and signs maintenance:**
`Street_Sweeping*`, `*street_sweeping*`, `Maintenance Subzones For Signs`, `*Signs` (maintenance layer)

**Administrative FEMA / census reference (not substantive planning layers):**
`*Map Index*`, `FEMA FIRM.*Map Index*`, `*Panel Index*`

**Census reference layers (raw census geography joins):**
`County Tracts` (standalone census reference), `Cities` (standalone reference list)

**Duplicate/legacy buffer geometry (prefer named policy layer):**
`HQTC_Buffer_HalfMile_LRStops_*` (raw geometry — prefer `SB 9 HQTC` or `Half Mile Buffer From High Quality Transit Corridor` as the named layer), `*HQTC*` (raw geometry intermediaries — exclude unless the service name itself is `SB9_HQTC` and the layer has a descriptive planning name, not a raw geometry name)

**Generic project/entitlement tracking (exclude ambiguous forms):**
`Projects` (exact match — too generic; prefer `Project Developments`, `Opportunity Sites`, or named entitlement layers), `Parking Lot` (planimetric infrastructure; exclude unless in confirmed planning service)

**Lead/water quality data:**
`LeadWater_Parcels*`, `Lead_Copper*`

---

## 5. Ambiguous / Context-Dependent Layers

| Layer Name | Ambiguity Reason | Resolution Rule |
|---|---|---|
| `Parking Designation Zones` | Could be Planning (zoning code) or Public Works | Include if service contains planning signals |
| `Parking Lots` / `Parking Restrictions` | Engineering or land use | Include only if in confirmed planning service |
| `Wetlands` | Environmental, GIS base, or planning overlay | Include if co-located with zoning/land use services |
| `Watersheds` / `Watershed Sub Basins` | Public Works or Planning overlay | Include if service name contains planning signals |
| `Neighborhoods` | Planning and general reference | Include if co-located with zoning or land use layers |
| `City Limits` / `City Boundary` | Base reference | Include as supporting/reference layer |
| `School Districts` | Planning reference vs. education admin | Include when in EnerGov, ComDev, CDD, or GeneralPlan service context |
| `Flood Zones` / `100 Year Flood` | FEMA base or planning-regulated overlay | Include when co-located with zoning/parcel layers; in NC/Southeast, floodplain administration is a planning function — include |
| `Voluntary Agricultural Districts` | Land use protection — NC/Southeast specific | Include — administered by county planning; land use policy mechanism |
| `Right of Way` | PW asset or planning land use boundary | Include only when in a planning-named service |
| `Project Developments` | Entitlement tracking or capital projects | Include when co-located with zoning/parcel layers or in CDD/Planning service |
| `Sphere of Influence` | LAFCO boundary — California | Include — urban growth/annexation planning boundary |
| `CFD Parcels` | Community Facilities District | Include when paired with parcel or zoning layers |
| `Transit Buffer` / `Transit Priority Areas` | Transit agency or planning overlay | Include when in CDD/Planning service or name includes housing/land use context |
| `FIRM Panels` | FEMA flood map panels | Include only with parcel/zoning co-occurrence; exclude `Map Index` variant always |
| `Contours` (5ft, 10ft, 20ft, 100ft, topo) | Base topographic data | Include for single-service county MapServers where contours are planning reference; include when co-located with slope/hazard/development restriction layers |
| `Steep Slopes` | Engineering or planning development restriction | Include — development restriction overlay when in planning service |
| `Easements` | Utility easements (PW) vs. conservation (Planning) | Include: `Conservation Easement`, `Agricultural Easement`, `Access Easement`. Exclude: `Utility Easement`, `Drainage Easement`, `Easement Boundary` (generic) |
| `Agricultural Districts` | State-designated or tax category | Include — planning land use protection in most states |
| `Airports` | Transportation infrastructure or land use compatibility | Include when layer represents Airport Influence Area, Compatibility Zone, or noise contour; exclude when simply a facility point |
| `Fire Districts` | Operational boundary or planning reference | Include — planning reference boundary when NOT in a Fire service folder |
| `Park Areas` / `Public Parks` | Parks facility layer or land use designation | Include — planning land use layer when NOT in a Parks operational service folder |
| `Building Outlines` | Engineering basemap or property reference | Include when in a parcel/assessor/planning service |
| `Address Point` | Utility record or planning geocoding reference | Include when in planning service or as the authoritative address reference for parcel matching |
| `Metro` | Transit district or administrative boundary | Include — transit district/authority boundary is a planning reference geography |
| `Neighborhood.*Associations` | Community organization or planning boundary | Include when in CDD/Planning service; lower confidence as standalone |
| `Inspector_Zones` | Permitting inspections — operational, not planning | Exclude — internal operational zone assignment |
| `Shopping Centers` | Retail inventory or land use | Include when in confirmed planning service (CDD/Planning); exclude standalone |
| `Wireless Telecomm Facilities` | Regulatory permit tracking or planning overlay | Include when in confirmed planning service; flag as low-priority standalone |
| `Low Income Housing` | Housing program layer | Include — affordable housing program is a planning function |
| `Landscape Lighting Maintenance Districts (LLMD)` | Public works maintenance or special district boundary | Include — special assessment district boundary is a planning/community dev reference |

---

## 6. URL Structure Patterns for Planning Services

### ArcGIS Online (Hosted Services) — Flat Structure
```
https://services[N].arcgis.com/[OrgID]/ArcGIS/rest/services/[ServiceName]/FeatureServer/[LayerIndex]
```
In AGOL orgs, each FeatureServer is individually named with no folder grouping. The service name IS the layer name for Tier 1 matching. Apply Tier 1 token matching directly against the service name string.

Planning-indicative service name patterns:
- Exact: `ComDev`, `Zoning`, `ZONING`, `Historic_District`, `Subdivisions`, `Parcels`, `TIF_Zones`, `Urban_Growth_Boundary`, `Specific_Plans`, `Opportunity_Sites`
- Contains: `Land_Use`, `MasterPlan`, `Plan`, `Agreement`, `Zoning`, `PLU`, `Housing`, `Development`, `Parcel`, `Historic`, `GeneralPlan`
- Suffix patterns: `_View`, `_ws`, `_SHP` appended to a planning term

### On-Premises / Self-Hosted ArcGIS Server — Folder Structure
```
https://gis.[jurisdiction].org/[server]/rest/services/[ServiceGroup]/[ServiceName]/MapServer/[LayerIndex]
```
Planning-indicative service group tokens: `EnerGov`, `ComDev`, `CDD`, `Planning`, `LandDev`, `CommunityDevelopment`, `CD`, `P_D`, `GeneralPlan`

When the ServiceGroup matches, ALL child services are presumptively planning-relevant; apply only Section 4.10 hard exclusions.

### Single-Service County MapServers
```
https://gis.[county].[state].us/arcgis/rest/services/[GenericServiceName]/MapServer/[LayerIndex]
```
Generic service names: `Website_Map_CityView`, `Website_Map`, `County_Parcels`, `PublicMap`, `PropertySearch`, `ParcelViewer`, `CityView`, `CountyGIS`, `PublicViewer`

**Crawler traversal rule:** When any layer in this service scores ≥ 1 on any Tier 2 cluster, enumerate ALL layers in the service and score each. Treat any layer scoring ≥ 2 as a planning candidate. Do not apply a service-level filter before layer-level scoring.

**Preferred service selection:** When a REST directory lists multiple services including a generic-named large MapServer alongside specialized services (e.g., `ForeclosureMap`, `basemap`, `InternalUse`), prioritize the large generic MapServer as the primary traversal target. Avoid `InternalUse` and `ForeclosureMap` as primary sources.

### EnerGov Platform (Tyler Technologies)
The service name `EnerGov` in a `MapServer` endpoint identifies a Tyler Technologies permitting and land management platform. All layers within an EnerGov service have high planning/community development relevance. Apply only Section 4.10 hard exclusions.

EnerGov-specific hard exclusions (add to Section 4.10 enforcement):
`History Point*`, `HistoryPolygon*`, `Spatial Polyline*`, `SpatialCollectionPolyline*`, `Location` (exact), `Converted_Graphics*`

---

## 7. Named Abbreviations and Acronyms Reference

| Abbreviation | Meaning | Planning Relevance |
|---|---|---|
| `ComDev` | Community Development | Department name — highest confidence |
| `CDD` | Community Development Department | Department folder — California |
| `GP` | General Plan | Zoning/land use policy document |
| `PLU` | Planned Land Use | Zoning/general plan layer |
| `UGB` | Urban Growth Boundary | Comprehensive planning tool |
| `TDR` | Transfer of Development Rights | Density bonus mechanism |
| `TIF` | Tax Increment Financing | Economic/redevelopment planning |
| `ESA` | Environmentally Sensitive Area | Environmental overlay in land use code |
| `NRHP` | National Register of Historic Places | Historic preservation planning |
| `PID` | Parcel ID | Cadastral key — planning reference |
| `EnerGov` | Tyler Technologies permitting platform | Planning/CD department platform |
| `ZCU` | Zoning Code Update | Active regulatory update layer |
| `BMR` | Below Market Rate | Affordable housing — California |
| `CFD` | Community Facilities District | Mello-Roos; tied to planned development — California |
| `HQTC` | High Quality Transit Corridor | California AB 2923 housing law planning overlay |
| `SOI` | Sphere of Influence | LAFCO urban growth boundary — California |
| `RHNA` | Regional Housing Needs Allocation | California housing element statutory quota |
| `VAD` | Voluntary Agricultural District | NC/Southeast land use protection |
| `ETJ` | Extraterritorial Jurisdiction | Southeast/Texas planning and annexation boundary |
| `UDO` | Unified Development Ordinance | Southeast integrated zoning/subdivision code |
| `FLUM` | Future Land Use Map | Comprehensive Plan map — Southeast/Midwest |
| `PUD` | Planned Unit Development | Development entitlement type |
| `SUP` | Special Use Permit | Conditional use entitlement |
| `TIRZ` | Tax Increment Reinvestment Zone | Texas economic development overlay |
| `LLMD` | Landscape Lighting Maintenance District | Special assessment district boundary |

---

## 8. Confidence Scoring Model

| Signal | Points |
|---|---|
| Tier 1: URL service path is `ComDev`, `CDD`, `EnerGov`, `Planning`, `GeneralPlan`, or exact department name | +5 |
| Tier 1: URL service path contains `Zoning`, `Land_Use`, `MasterPlan`, `Historic`, `Subdivision`, `TIF`, `PLU`, `HousingElement`, `Specific_Plans`, `Opportunity_Sites`, `Urban_Growth` | +4 |
| Tier 1: URL service path contains `Development`, `Agreement`, `Growth`, `Plan`, `LandDev`, `ZCU`, `FLUM` | +3 |
| Tier 2: Layer name contains 3+ keywords from a single semantic cluster (A–I) | +3 |
| Tier 2: Layer name contains 1–2 keywords from clusters A–F | +2 |
| Tier 2: Layer name matches Cluster I (Hazards/Development Restrictions) — standalone | +2 |
| Tier 2: Layer name contains administrative geography keyword (Cluster G) | +1 |
| Tier 2: Layer name matches Cluster J (Landmarks/Civic Features) — requires co-occurring Tier 1 or Tier 2 A–I signal | +1 |
| Exclusion: URL service path matches Public Works, Fire, Utilities, or Business License token | -5 |
| Exclusion: Layer name matches Section 4.10 hard exclusion pattern | -10 (override) |
| Exclusion: Layer name matches business license type | -4 |
| Exclusion: Layer name matches utility infrastructure | -3 |

**Interpretation:**
- Score ≥ 4: Include (high confidence)
- Score 2–3: Include as likely planning layer (moderate confidence)
- Score 0–1: Ambiguous — apply cluster co-occurrence test
- Score ≤ -1: Exclude
- Score = -10: Hard exclusion — no override

---

## 9. Representative Layer Examples from Source Data

### Confirmed Planning Layers (Score ≥ 4)

| Layer Name | Service | Jurisdiction | Reason |
|---|---|---|---|
| Zoning | `ComDev` | Aspen CO | Tier 1 + core planning content |
| Historic Districts | `ComDev` | Aspen CO | Tier 1 + Cluster D |
| Future Land Use | `Future_Land_Use_2012` | Las Vegas NV | Tier 1 + Cluster A |
| Subdivisions | `EnerGov` | Grand Prairie TX | Tier 1 platform + Cluster B |
| Housing Element Sites (By-Right) | `CDD/HousingElement` | Sunnyvale CA | Tier 1 CDD + Cluster B |
| SpecificPlans | `CDD/HousingElement` | Sunnyvale CA | Tier 1 CDD + Cluster C |
| Specific Plan Area Boundary | `ZoningLegend` | Sunnyvale CA | Cluster C exact match |
| Combining District | `ZoningLegend` | Sunnyvale CA | Cluster A |
| Council Districts | `LRS` | Sunnyvale CA | Cluster G |
| Downtown Street Character | `CDD/CDDother` | Sunnyvale CA | Tier 1 CDD + Cluster C/A |
| Downtown Specific Plan Boundary | `CDD/CDDother` | Sunnyvale CA | Tier 1 CDD + Cluster C |
| Neighborhood Planning Areas | `CDD/CDDother` | Sunnyvale CA | Tier 1 CDD + Cluster C |
| Park Facilities | `GeneralPlan` | Sunnyvale CA | Tier 1 GeneralPlan + Cluster J co-occurring |
| Horizon 2035 GP LandUse | `GeneralPlan` | Sunnyvale CA | Tier 1 GeneralPlan + Cluster A (GP abbreviation) |
| School Districts | `EnerGov` | Sunnyvale CA | Tier 1 EnerGov + Cluster G |
| ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A — single-service MapServer |
| MUNICIPAL ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A |
| COUNTY ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A |
| MOUNT AIRY HISTORIC DISTRICT | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster D |
| MOUNT AIRY LOCAL HISTORIC DISTRICT | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster D |
| MOUNT AIRY NATIONAL HISTORIC DISTRICT | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster D |
| VOLUNTARY AGRICULTURAL DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster B |
| VOLUNTARY AGRICULTURAL PARCELS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster B/F |
| VOLUNTARY AGRICULTURAL PARCELS HALF MILE BUFFER | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster I |
| FLOOD ZONES | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster E/I |
| 100 YEAR FLOOD | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster E/I |
| 500 YEAR FLOOD | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster E/I |
| 100 YEAR FLOOD FLOODWAY | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster E/I |
| CONTOURS (5Ft / 10 Ft / 20 Ft / 100Ft) | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster I — single-service MapServer |
| WATERSHEDS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster E/I |
| COUNTY BOUNDARY | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| MUNICIPALITIES | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| ADJACENT COUNTIES | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| PARCELS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster F |
| PARCEL DIMENSIONS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster F |
| CENSUS TRACTS 2010 | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G — boundary layer |
| VOTING DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| TOWNSHIPS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| ZIP CODES | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| ELEMENTARY SCHOOL DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| MIDDLE SCHOOL DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| HIGH SCHOOL DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G |
| FIRE RESPONSE DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G — planning reference boundary, not in Fire service |
| FIRE TAX DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster G — tax district boundary |
| RIVERS, LAKES, AND PONDS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster I |
| RIVERS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster I |
| STREAMS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster I |
| CEMETERIES | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster J — co-occurring with planning service |
| Assessor Parcels | AGOL | Milpitas CA | Tier 1 `Assessor.*Parcel` + Cluster F |
| Zoning By Parcel | AGOL | Milpitas CA | Tier 1 `Zoning` + Cluster F |
| Planned Unit Development | AGOL | Milpitas CA | Tier 1 pattern + Cluster B |
| Specific Plans | AGOL | Milpitas CA | Tier 1 `Specific_Plans` + Cluster C |
| Urban Growth Boundary | AGOL | Milpitas CA | Tier 1 `UGB`/`Growth` + Cluster C |
| Milpitas Historical Inventory | AGOL | Milpitas CA | Cluster D — `Historical Inventory` |
| City Boundary | AGOL | Milpitas CA | Cluster G |
| Neighborhoods of Milpitas | AGOL | Milpitas CA | Cluster G — `Neighborhoods of.*` |
| CFD Parcels | AGOL | Milpitas CA | Cluster B/F |
| Fire Districts | AGOL | Milpitas CA | Cluster G/B — planning reference boundary; NOT in Fire service |
| Park Areas | AGOL | Milpitas CA | Cluster B — land use designation; NOT in Parks operational service |
| Public Parks | AGOL | Milpitas CA | Cluster B/J — NOT in Parks operational service |
| Building Outlines | AGOL | Milpitas CA | Cluster F — property reference |
| Address Point Public Safety | AGOL | Milpitas CA | Cluster F — authoritative address reference |
| FEMA Flood Zone Polygons | AGOL | Milpitas CA | Cluster E/I — substantive flood layer |
| Land Use Overlay Exception | AGOL | Milpitas CA | Tier 1 `Land_Use` + `Overlay` — Cluster A |
| Landscape Lighting Maintenance Districts (LLMD) | AGOL | Milpitas CA | Cluster G — special assessment district boundary |
| Metro | AGOL | Milpitas CA | Cluster G — transit district boundary |
| Public Owned Land | AGOL | Milpitas CA | Cluster G — public land ownership boundary |
| Low Income Housing | AGOL | Milpitas CA | Cluster B — affordable housing program |

### Excluded Layers (Score ≤ -1 or Hard Exclusion)

| Layer Name | Service | Jurisdiction | Reason |
|---|---|---|---|
| Gaming Restricted (1-5 Slots) | `LIVE_CLV_BUS` | Las Vegas NV | Business license record |
| Phantoms - Fire Map | `FD_PHANTOMS_View` | Las Vegas NV | Fire operational |
| PW Bike Trails Status | `PW_Bike_Trails` | Clark County NV | Public Works infrastructure |
| Pavement Condition / Pavement_Index | AGOL | Milpitas CA | PW asset management — excluded by name regardless of service |
| Street_Sweeping_Pilot_Areas | AGOL | Milpitas CA | Section 4.10 hard exclusion `Street_Sweeping*` |
| History Point - Since 2022/10/31 | `EnerGov` | Sunnyvale CA | Section 4.10 hard exclusion — EnerGov internal |
| HistoryPolygon | `EnerGov` | Sunnyvale CA | Section 4.10 hard exclusion |
| Spatial Polyline | `EnerGov` | Sunnyvale CA | Section 4.10 hard exclusion |
| SpatialCollectionPolyline | `EnerGov` | Sunnyvale CA | Section 4.10 hard exclusion |
| Location | `EnerGov` | Sunnyvale CA | Section 4.10 hard exclusion |
| Converted_Graphics | `CDD` | Sunnyvale CA | Section 4.10 hard exclusion |
| CityWide.SDE.i_DOTAT | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 hard exclusion |
| Default | `CDD` | Sunnyvale CA | Section 4.10 hard exclusion |
| Feature.MAPREAD.AP_Parcels | AGOL | Milpitas CA | Section 4.10 hard exclusion `Feature.MAPREAD.*` |
| Feature.MAPREAD.BL_FloodZone | AGOL | Milpitas CA | Section 4.10 hard exclusion |
| LeadWater_Parcels_all | AGOL | Milpitas CA | Section 4.10 hard exclusion |
| HQTC_Buffer_HalfMile_LRStops_2019_Dec | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 — raw geometry intermediary |
| FEMA FIRM - Map Index | `FloodZones` | Sunnyvale CA | Section 4.10 `*Map Index*` |
| annotation_parcels | `InternalUse` | Surry NC | Section 4.10 `*anno*` + InternalUse service |
| lot_anno | `InternalUse` | Surry NC | Section 4.10 `*anno*` |
| Bus_Routes_and_Stops_January_2020 | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 transit operational data |
| BusStops_Jul2016_SunnyvaleOnly | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 transit operational data |
| BusStops_Jan2015_VTAOpenData | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 transit operational data |
| VTALRTStn | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 transit station point |
| caltrain_stations_project | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 transit station point |
| Lawrence_Station | `CDD/SB9_HQTC` | Sunnyvale CA | Section 4.10 `*_Station` |
| Inspector_Zones | `EnerGov` | Sunnyvale CA | Operational inspection zone assignment |
| Tracfic_Impact_Fee | `EnerGov` | Sunnyvale CA | Typo/internal fee calculation layer |
| AIRPORTS | `Website_Map_CityView` | Surry County NC | Facility point only — no compatibility overlay context |
| FIRE HYDRANTS | `Website_Map_CityView` | Surry County NC | Section 4.2 hard name exclusion |
| FIRE HYDRANTS AND WATER POINTS | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| FIRE WATER POINTS | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| RAILROADS | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| HWY LABELS | `Website_Map_CityView` | Surry County NC | Section 4.2 + Section 4.10 label |
| STRUCTURES | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| BUILDING FOOTPRINTS | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| ROADS | `Website_Map_CityView` | Surry County NC | Section 4.2 |
| ROAD | `Website_Map_CityView` | Surry County NC | Section 4.2 |

---

## 10. Regional Terminology Reference

### California
| Term | Meaning | Cluster |
|---|---|---|
| `Housing Element` | Mandatory General Plan element | B, C |
| `RHNA` / `RHNA Sites` | Regional Housing Needs Allocation | B |
| `Specific Plan` / `Precise Plan` | Subarea regulatory plan | C |
| `Sphere of Influence (SOI)` | LAFCO-designated urban growth boundary | C, G |
| `HQTC` / `High Quality Transit Corridor` | AB 2923 transit-oriented overlay | C |
| `Transit Priority Area` | Half-mile buffer around major transit stops | C |
| `SB 9 Overlay` / `AB 2923 Zone` | State law two-unit/lot-split overlays | A, B |
| `ADU.*Overlay` / `Accessory Dwelling` | ADU applicability zones | A, B |
| `BMR` / `Below Market Rate` | Affordable housing program | B |
| `CFD` / `CFD Parcels` | Community Facilities District — Mello-Roos | B, F |
| `Mello-Roos` | Mello-Roos district boundary | B, F |
| `Hillside Building Code` | Hillside development standards overlay | A |
| `GP LandUse` / `GP Land Use` | General Plan Land Use designation layer | A, C |
| `Combining District` / `Combining_Districts` | Zoning overlay that supplements base zone | A |
| `LLMD` | Landscape Lighting Maintenance District | G |

### Southeast (NC, SC, GA, FL, TN, AL, MS, VA)
| Term | Meaning | Cluster |
|---|---|---|
| `UDO` | Unified Development Ordinance | A |
| `ETJ` | Extraterritorial Jurisdiction | G |
| `Voluntary Agricultural District (VAD)` | NC/VA farmland protection | B |
| `FLUM` | Future Land Use Map | A, C |
| `Sector Plan` | Subarea comprehensive plan | C |
| `TND` | Traditional Neighborhood Development | A |
| `Voluntary Agricultural Parcels Half Mile Buffer` | VAD protection buffer — NC specific | I |
| `Website_Map_CityView` | Primary public MapServer — traverse fully | Single-service rule |

### Midwest (OH, IN, IL, MI, WI, MN, IA, MO)
| Term | Meaning | Cluster |
|---|---|---|
| `Comprehensive Plan` | Equivalent of General Plan | C |
| `FLUM` | Future Land Use Map | A, C |
| `Township` | Civil township boundary | G |
| `TIF District` | Tax Increment Financing | B |
| `PUD` | Planned Unit Development | B |
| `Annexation.*Boundary` | Municipal growth boundary | B, G |

### Southwest / Mountain West (AZ, NM, CO, NV, UT, ID, WY, MT)
| Term | Meaning | Cluster |
|---|---|---|
| `PAD` | Arizona Planned Area Development | B, C |
| `Wildfire Hazard` / `WUI` | Planning-regulated overlay | E |
| `View Corridor` / `Viewshed` | Scenic protection overlay | C, E |

### Texas
| Term | Meaning | Cluster |
|---|---|---|
| `ETJ` | Extraterritorial Jurisdiction | G |
| `PDD` | Planned Development District | B |
| `TIRZ` | Tax Increment Reinvestment Zone | B |
| `Annexation.*Schedule` | City annexation plan | B, G |

---

*Analysis based on 300+ layers from 7+ municipal/county ArcGIS environments: City of Aspen CO (ComDev), City of Grand Prairie TX (EnerGov), City of Dublin OH, Clark County / City of Las Vegas NV, Surry County NC (Website_Map_CityView), City of Sunnyvale CA (CDD, EnerGov, GeneralPlan), and City of Milpitas CA (ArcGIS Online AGOL).*

*Version 3.0 changes: Added Principle 0 design principles block; added GeneralPlan/General_Plan as Tier 1 tokens; rewrote Section 4 exclusions to use service-domain logic (exclude service, not layer name); added Section 4.10 hard exclusion patterns covering EnerGov platform internals, annotation classes, imagery, transit operational data, Map Index layers, and ambiguous standalone names; added `GP`, `LLMD`, `TIRZ` to acronym table; added `Downtown Street Character`, `Floodways Channels/Creeks`, `Neighborhood Planning Areas`, `Building Outlines`, `Address Point`, `Public Owned Land`, `Metro`, `Combining District`, `Fire Districts/Park Areas/Public Parks` (contextual inclusion) to clusters; added full Surry County representative examples; expanded single-service MapServer traversal rules with generic service name list and preferred service selection guidance; clarified Cluster J co-occurrence requirement as hard enforcement rule.*
