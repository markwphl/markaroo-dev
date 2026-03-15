# Planning Department GIS Layer Pattern Analysis
**Source:** 300+ ArcGIS REST service layers across 7 municipal/county GIS environments  
**Version:** 2.2 — v2.1 plus Hazards/Development Restrictions cluster, Administrative Boundaries expansion, and Landmarks/Civic Features cluster  
**Purpose:** Equip an LLM with structured markers to identify layers associated with Planning Departments, Planning Commissions, and Community Development Departments in local government ArcGIS applications.

---

## 1. How to Use This Guide

This document defines a three-tier classification system. Apply markers in order of precedence:

1. **URL Service Path Signals** — strongest single indicator; comes directly from how the GIS admin named the service
2. **Layer Name Keyword Signals** — second strongest; reflects the content domain
3. **Exclusion Signals** — used to suppress false positives from departments that share terminology with planning

A layer qualifies as a **Planning department layer** when it satisfies one or more Tier 1 signals, OR two or more Tier 2 signals, AND does not trigger an Exclusion signal.

### Structural Notes Before Applying the Rules

**Single-service county MapServers:** Smaller counties (population < 100k) often publish a single all-purpose `MapServer` with a generic name (e.g., `Website_Map_CityView`, `County_Parcels`, `PublicMap`). When no Tier 1 signal fires in the service name, apply Tier 2 keyword clustering directly to all layer names. Any layer scoring ≥ 2 in a mixed-department single service should be flagged for review rather than auto-excluded.

**ArcGIS Online (AGOL) flat FeatureServer lists:** AGOL orgs present 50–300 individually-named FeatureServer services with no folder hierarchy. Each service name IS effectively the layer name for classification. Apply Tier 1 token matching directly against the service name string. Tier 2 cluster matching applies normally. Do not require a folder-level signal before applying Tier 2 rules — the flat structure is the expected pattern, not an anomaly.

**Folder-organized on-prem servers:** When the REST directory uses `[ServiceGroup]/[ServiceName]` two-level naming, the ServiceGroup is the strongest Tier 1 signal. A CDD, Planning, or ComDev folder elevates all child services to high confidence regardless of individual service names.

---

## 2. Tier 1 — URL Service Path Signals (Highest Confidence)

These strings appear in the `/services/` segment of the ArcGIS REST endpoint URL. When present, they are near-definitive evidence of a Planning or Community Development service, regardless of layer name.

### Explicit Department Identifiers
These tokens directly name the department:

| Token | Example URL Fragment | Notes |
|-------|---------------------|-------|
| `ComDev` | `/services/ComDev/FeatureServer/` | Community Development — canonical abbreviation; West/Southwest |
| `CDD` | `/services/CDD/HousingElement/MapServer/` | Community Development Department — California common abbreviation |
| `Planning` | `/services/Planning/Zoning/MapServer/` | Direct department name as folder; common in Midwest/Southeast |
| `LandDev` | `/services/LandDev/Subdivisions/MapServer/` | Land Development folder; common in Southeast |
| `CommunityDevelopment` | `/services/CommunityDevelopment/FeatureServer/` | Full department name; common in smaller jurisdictions |
| `EnerGov` | `/services/EnerGov/DisplayMap/MapServer/` | Tyler EnerGov permitting/planning platform; always planning-adjacent |
| `PLU` | `/services/CLV_PLU/FeatureServer/` | "Planned Land Use" — planning-specific abbreviation |
| `ROIS` | `/services/ROIS/FeatureServer/` | Regional/municipal overlay index system; planning context |

### Land Use and Zoning Service Names
| Token / Pattern | Notes |
|----------------|-------|
| `Zoning` / `ZONING` | Any case variant |
| `ZCU` | Zoning Code Update — active regulatory update service |
| `Land_Use` / `LandUse` / `_LU_` | Standalone or embedded in longer service name |
| `Future_Land_Use` | General Plan / Comprehensive Plan layer |
| `General_Plan` | General Plan document layers |
| `Residential_Zoning` | Zoning sub-category |
| `MasterPlan` / `Master_Plan` | Any master plan boundary or district |
| `Master_Planned_Communities` | Planned unit development context |
| `Downtown.*Plan` / `DTMasterPlan` | Downtown-specific planning documents |
| `Envision_.*_Land_Use` | Named comprehensive plan services |
| `Growth_Framework` | Urban growth policy layer |
| `Form.Based.Code` | Form-based zoning regulatory layer |
| `HousingElement` | California statutory General Plan element service |
| `Comprehensive_Plan` | Midwest/Southeast equivalent of General Plan |
| `FLUM` | Future Land Use Map — common in Southeast/Midwest |

### Parcel and Property Services
| Token / Pattern | Notes |
|----------------|-------|
| `Parcels` / `PARCELS` | Base cadastral layer; core to planning workflow |
| `CC_PARCELS` / `CLV_PARCELS` | Jurisdiction-prefixed parcel services |
| `TIF_Parcels` / `TIF_Zones` | Tax Increment Financing — economic development/planning |
| `Assessor.*Parcel` / `PARCELS_SHP` | Assessor parcel geometry |
| `Mello_Roos` / `MelloRoos` / `Mello-Roos` | CFD financing boundary; GIS admins frequently use this name rather than CFD — California |

### Development Activity Services
| Token / Pattern | Notes |
|----------------|-------|
| `Development_Agreement` / `Agreement_Areas` | Binding land development agreements |
| `Outside_.*_Development` | Fringe area development tracking |
| `Subdivision` / `Subdivision_Sections` | Subdivision plat management |
| `Special_Area_Plan` / `Special_Area_Boundaries` | Subarea planning |
| `Specific_Plans` / `SpecificPlans` | California term for special area plans |
| `Precise_Plan` / `PrecisePlan` | California term; subarea regulatory plan |
| `Opportunity_Sites` | Housing element / redevelopment site inventory |
| `HousingElement` | California statutory planning document |
| `Urban_Growth_Boundary` / `UGB` | Growth boundary service |

### Historic Preservation Services
| Token / Pattern | Notes |
|----------------|-------|
| `Historic_District` | District boundary designation |
| `Historic_District_Structure_Info` | Individual structure inventory |
| `NRHP_Boundary` | National Register of Historic Places — preservation planning |
| `Historic.*Inventory` | Historic resource survey layer |

---

## 3. Tier 2 — Layer Name Keyword Signals (Medium-High Confidence)

These terms appear in the layer name itself. No single term below is conclusive alone; confidence increases with co-occurrence. Three or more terms from the same semantic cluster = high confidence.

### Cluster A: Zoning and Land Use Regulation
Keywords: `Zoning`, `Zone`, `Zone Overlay`, `Zone Map`, `Overlay`, `Land Use`, `Future Land Use`, `General Plan`, `Comprehensive Plan`, `FLUM` (Future Land Use Map), `Planned Development`, `Form-Based Code`, `Infill`, `Residential Zoning`, `Non Attainment`, `UGB` (Urban Growth Boundary), `Zoning Code Update`, `ZCU`, `Hillside.*Code`, `Hillside.*Regulation`, `Heights` (building height limits = zoning regulation), `Tree.*Zone` (tree preservation = zoning code), `SB 9.*Overlay`, `AB 2923.*Zone`, `Two-Unit.*Overlay`, `Lot Split.*Zone`, `State Density Bonus`, `Ministerial.*Zone`, `ADU.*Overlay`, `ADU.*Zone`, `Accessory Dwelling`, `Junior ADU`

### Cluster B: Development Review and Entitlements
Keywords: `Subdivision`, `Subdivisions`, `Subdivision Sections`, `Special Use Permit`, `Development Agreement`, `Agreement Area`, `PACE Agreement`, `TDR` (Transfer of Development Rights), `TIF` (Tax Increment Financing), `Annexation`, `Annex`, `Deannex`, `Outside.*Development`, `Planned Development`, `Planned Unit Development`, `PUD`, `Housing Element`, `Housing Element Sites`, `By-Right`, `Opportunity Sites`, `Project Development`, `Project Developments`, `Project Pipeline`, `Innovation.*Parcel`, `BMR` (Below Market Rate housing), `Below Market Rate`, `Low Income Housing`, `Affordable Housing`, `CFD` (Community Facilities District as parcel overlay), `CFD Parcels`, `Mello-Roos`, `Mello_Roos`, `VAD` (Voluntary Agricultural District), `Voluntary Agricultural.*District`, `Voluntary Agricultural.*Parcel`, `RHNA`, `RHNA Sites`, `RHNA Allocation`, `Rezoning.*RHNA`

### Cluster C: Comprehensive / Master Planning
Keywords: `Master Plan`, `Master Planned`, `General Plan`, `Comprehensive Plan`, `Future Land Use`, `Growth Framework`, `Character Areas`, `Special Area Plan`, `Specific Plans`, `Precise Plan`, `Precise Plan Area`, `Civic Master Plan`, `Downtown.*Plan`, `Town Center.*Plan`, `Viewplane`, `Mtn Viewplane`, `Greenline`, `Sphere of Influence`, `Urban Growth Boundary`, `Transit Priority Area`, `High Quality Transit Corridor`, `HQTC`, `Transit Buffer`, `Midtown.*Boundary`, `Corridor Plan`, `Small Area Plan`, `Area Plan`, `Sector Plan` (Southeast/Midwest term for subarea plan)

### Cluster D: Historic Preservation
Keywords: `Historic District`, `Historic Sites`, `Historic Buildings`, `Historic Inventory`, `NRHP`, `Character Areas`, `Landmark`, `Local Historic District`, `National Historic District`, `Heritage District`, `Preservation District`

### Cluster E: Environmental Overlay (Planning-Regulated)
Keywords: `Stream Margin`, `Wildfire Hazard`, `Wildfire District`, `Wildfire Zone`, `Wildfire.*Buffer`, `Fire Zone`, `Fire.*Buffer`, `WUI` (Wildland-Urban Interface), `ESA` (Environmentally Sensitive Area), `Hallam Bluff`, `Non Attainment`, `Wetlands`, `Wetland Buffer`, `Riparian Buffer`, `Riparian Zone`, `Riparian Corridor`, `Watershed` (when paired with overlay/planning context), `Soils` (when paired with land use context), `Flood Zone`, `Floodplain`, `Floodway`, `Flood.*Plain`, `FEMA Flood`, `FEMA Floodplain`, `100 Year Flood`, `100-Year Flood`, `500 Year Flood`, `500-Year Flood`, `100 Year Floodway`, `Special Flood Hazard Area`, `SFHA`, `Flood Zone Parcels`, `Tree Preservation`, `Tree Canopy.*Regulation`, `Agricultural.*Buffer`, `Conservation.*Easement`, `Earthquake Zone`, `Seismic Zone`, `Seismic Hazard`, `Tsunami Zone`, `Tsunami Hazard`, `Liquefaction Zone`, `Steep Slope`, `Slope.*Hazard`, `Landslide.*Zone`, `Geologic Hazard`

### Cluster F: Cadastral and Property Reference
Keywords: `Parcels`, `Assessor Parcels`, `PID` (Parcel ID), `TIF Parcels`, `CFD Parcels`, `BMR Parcels`, `Flood Zone Parcels`, `Religious.*Parcel`, `Building Footprints.*Landuse`, `Lot`, `Parcel Owner`, `Parcel Report`, `Innovation.*Parcel`, `Right of Way` (when in planning platform context)

### Cluster G: Administrative Boundaries
Keywords: `Neighborhoods`, `Neighborhood Boundary`, `City Limits`, `City Boundary`, `Municipal Boundary`, `Municipalities`, `County Boundary`, `County Line`, `Adjacent Counties`, `Wards`, `Council Wards`, `ZIP Codes`, `Zipcodes`, `Zip Code Boundaries`, `Census Tracts`, `Voting Districts`, `Election Districts`, `Precincts`, `School Districts`, `School Catchment`, `School Attendance Zone`, `School Boundary`, `Township`, `ETJ` (Extraterritorial Jurisdiction — Southeast/Texas common), `UDO` (Unified Development Ordinance boundary — Southeast), `Sphere of Influence`

### Cluster H: Regulatory Use Restrictions
Keywords: `Billboard Buffer`, `Billboards Exclusionary Zone`, `Outdoor Lighting Code`, `Short Term Rental`, `Prohibited Area`, `Resort Hotels`, `Small Cell Wireless`, `Cell Towers`, `Scenic Byway`, `Pedestrian Mall`, `Gaming.*Overlay`, `Gaming.*District` (regulatory boundary, not license record), `Community Residence`, `Symphony.*District`, `Alcohol.*Buffer` (regulatory buffer around schools/churches — planning-administered), `Adult.*Use.*Overlay`, `Cannabis.*Overlay`, `Noise.*Contour` (when in land use context)

### Cluster I: Hazards and Development Restrictions
This cluster covers layers that define where development is prohibited, restricted, or subject to special review. These are planning-relevant when they inform permit decisions, zoning overlays, or general plan policies — regardless of which department hosts them.

Keywords: `Floodplain`, `Flood Plain`, `Flood Zone`, `Floodway`, `Flood.*Area`, `100 Year Flood`, `100-Year Flood`, `100 Year Floodway`, `500 Year Flood`, `500-Year Flood`, `FEMA Flood`, `FEMA Floodplain`, `Special Flood Hazard Area`, `SFHA`, `FIRM`, `Fire Zone`, `Fire Hazard`, `Fire.*Buffer`, `Wildfire`, `Wildfire District`, `Wildfire Zone`, `Wildfire Hazard`, `WUI`, `Earthquake Zone`, `Seismic Zone`, `Seismic Hazard`, `Liquefaction`, `Tsunami Zone`, `Tsunami Hazard`, `Geologic Hazard`, `Steep Slope`, `Slope.*Restriction`, `Slope.*Overlay`, `Landslide`, `Erosion.*Zone`, `Contour` (when paired with development restriction context), `10.*Foot.*Contour`, `100.*Foot.*Contour`, `Topo.*Contour`, `Wetlands`, `Wetland.*Buffer`, `Wetland.*Setback`, `Riparian Buffer`, `Riparian Zone`, `Riparian Corridor`, `Stream.*Buffer`, `Stream.*Setback`, `River.*Buffer`, `Waterbody.*Setback`, `Rivers`, `Streams`, `Ponds`, `Lakes`, `Waterbodies`, `Water.*Bodies`, `Hydrology`, `Conservation Easement`, `Easement`, `Agricultural District`, `Right to Farm`, `RTF Zone`, `RTF District`, `Farm.*Buffer`

### Cluster J: Landmarks and Civic Features
Landmarks are planning-relevant as reference layers in site analysis, general plan maps, and community facilities planning. They qualify as supporting layers when co-located with planning services; do not use as standalone planning evidence without Tier 1 or other Tier 2 signals.

Keywords: `High School`, `Middle School`, `Elementary School`, `Public School`, `School.*Location`, `School.*Point`, `School.*Site`, `Parks`, `Park.*Location`, `Park.*Point`, `Civic.*Area`, `Civic.*Center`, `City Hall`, `County.*Hall`, `County.*Courthouse`, `Courthouse`, `Fire Station`, `Police Station`, `Library`, `Community Center`, `Transit Stop`, `Transit Node`, `Bus Stop`, `Light Rail Stop`, `Train Station`, `Commuter Rail`, `Airport`, `Rivers`, `Streams`, `Lakes`, `Lakefront`, `Waterfront`, `Water.*Feature`, `Fountain`, `Playground`, `Ball Field`, `Athletic Field`, `Stadium`, `Sports Complex`, `Recreation.*Area`, `Open Space`, `Greenway`


---

## 4. Exclusion Signals — High-Confidence Non-Planning Indicators

When the following signals are present **without** accompanying Tier 1 or Tier 2 planning signals, the layer is likely owned by a different department and should be excluded.

### Imagery
Layer name keywords: 'aerial imagery', 'photos', 'historical imagery', 'basemap', 'anno', 'anno_1', 'label',

### Public Works / Transportation
Service name tokens: `PW_`, `SCL`, `RTC_`, `Bus_Stops`, `LIVE_SCL`, `DPW`, `PublicWorks`  
Layer name keywords: `Bike Trails`, `Bicycle Lane`, `Bicycle Route`, `Equestrian Trails`, `Trail Crossing`, `Trailheads`, `Trail Projects`, `Trails Network`, `Bus Stops`, `Pavement Condition`, `Pavement Index`, `Street Sweeping`, `Guardrails`, `Handicap Ramps`, `Street Lights`, `Traffic Signal`, `Truck Routes`, `Crossroads`, `Street Centerlines`, `Road Closures`

### Fire / Emergency Services
Service name tokens: `FD_`, `PHANTOMS`, `Fire_`, `EMS_`  
Layer name keywords: `Fire Map`, `Phantoms`, `Emergency`, `EMS`, `Fire Districts`, `Fire Pre Plan`, `Fire Run`, `Fire Stations`, `Fire Incidents`

### Business License / Revenue
Service name tokens: `LIVE_CLV_BUS`, `CLV_BUS`, `Business_License`  
Layer name keywords: `Business Licenses`, `Active Business Licenses`, `Gaming Restricted`, `Gaming Non-Restricted`, `Alcohol On-Premise`, `Alcohol Off-Premise`, `Massage Establishment`, `Marijuana Establishments`, `Daily Labor Service`, `Financial Institution`, `Restaurants` (as license record), `Amusement Park` (as license record), `Open Air Vending`, `Alcohol Beverage Control License`

### Parks and Recreation
Service name tokens: `Parks_Protected_Use`, `Pools_View`, `Community_Centers_View`  
Layer name keywords: `Parks` (standalone, no land use/planning qualifier), `Pools`, `Community Centers`, `Park Areas`, `Park Lights`, `Park Pathways`, `Park Points`, `Public Parks`

### Utilities
Service name tokens: `Utilities`, `Water_`, `Sewer_`, `Storm_`, `Stormwater_`, `Recycled_Water`, `Lucity`  
Layer name keywords: `Water Hydrant`, `Water Meter`, `Water Service`, `Sewer`, `Sanitary`, `Storm Drain`, `Recycled Water`, `Irrigation Controller`, `Backflow`, `Odor Sample`

### Schools (standalone, not as planning reference)
Service name tokens: `CCSD_Schools`, `PrivateSchools_ws`  
Layer name keywords: `CCSD Schools`, `Private Schools`, `School Points` (standalone)

### Police / Public Safety (standalone)
Service name tokens: `Police_`, `Mark43_`  
Layer name keywords: `Police Beats`, `Police Traffic Citations`, `Crime`, `Reporting Districts` (police), `Tiburon Reporting Districts`

---

## 5. Ambiguous / Context-Dependent Layers

These layers appeared in planning-adjacent services but require context to classify definitively.

| Layer Name | Ambiguity Reason | Resolution Rule |
|-----------|-----------------|----------------|
| `Parking Designation Zones` | Could be Planning (zoning code) or Public Works | Include if service name contains planning signals |
| `Parking Lots` / `Parking Restrictions` | Could be engineering or land use | Include only if service is in planning platform |
| `Wetlands` | Could be environmental, GIS base, or planning overlay | Include if co-located with zoning/land use services |
| `Soils` | Typically base GIS, but used in land capability planning | Include only with Cluster A/B co-occurrence |
| `Woodlots` | Environmental or planning tree canopy regulation | Include if in planning-named service |
| `Watersheds` / `Watershed Sub Basins` | Could be Public Works or Planning overlay | Include if service name contains planning signals |
| `Neighborhoods` | Used in both planning and general reference | Include if co-located with zoning or land use layers |
| `City Limits` / `City Boundary` | Base reference layer, used across all departments | Include only as supporting/reference layer |
| `School Districts` | Planning reference vs. education admin | Include when in EnerGov, ComDev, or CDD service context |
| `Scenic Byway` | Could be transportation or planning overlay | Include — regulatory overlay with land use implications |
| `Flood Zones` / `100 Year Flood` | Could be FEMA base layer or planning-regulated overlay | Include when co-located with zoning/parcel layers or in NC/Southeast where floodplain administration is a planning function |
| `Voluntary Agricultural Districts` | Land use protection program — NC/Southeast specific | Include — administered by county planning or soil & water offices; land use policy mechanism |
| `Right of Way` | Could be PW asset or planning land use boundary | Include only when in a planning-named service |
| `Projects` / `Project Developments` | Generic; could be capital projects (PW) or entitlements (Planning) | Include when co-located with zoning/parcel layers or in CDD/Planning service context |
| `Sphere of Influence` | LAFCO boundary — California specific | Include — this is an urban growth/annexation planning boundary |
| `CFD Parcels` | Community Facilities District — financing tool tied to planned development | Include when paired with parcel or zoning layers |
| `Transit Buffer` / `Transit Priority Areas` | Could be transit agency data or planning overlay | Include when in CDD/Planning service or when name includes housing/land use context |
| `FIRM Panels` | FEMA flood map administrative panels | Include only with parcel/zoning co-occurrence; exclude as standalone |
| `ETJ` (Extraterritorial Jurisdiction) | Southeast/Texas boundary — sometimes in planning, sometimes general reference | Include — ETJ is a planning/annexation jurisdiction boundary |
| `Contours` (10ft, 100ft, topo) | Base topographic data — used by all departments | Include when in a planning service or when co-located with slope/hazard/development restriction layers |
| `Steep Slopes` | Could be engineering analysis or planning development restriction overlay | Include — development restriction overlay when in planning service; flag as moderate when standalone |
| `Easements` (generic) | Could be utility easements (PW) or conservation/land use easements (Planning) | Include only when name specifies `Conservation Easement`, `Agricultural Easement`, or `Access Easement`; exclude `Utility Easement`, `Drainage Easement` |
| `Agricultural Districts` | Could be state-designated ag district (planning) or tax assessment category | Include — planning land use protection mechanism in most states |
| `Right to Farm` / `RTF Zone` | Agricultural land use protection — zoning/planning administered | Include — planning/zoning regulatory layer |
| `Rivers` / `Streams` / `Lakes` / `Waterbodies` | Base hydrology reference or environmental overlay | Include as supporting/reference when in planning service; exclude as standalone base layer |
| `Airports` | Could be transportation infrastructure (PW) or land use compatibility overlay (Planning) | Include when layer represents an Airport Influence Area, Airport Compatibility Zone, or noise contour; exclude when it is simply a point/facility location |
| `Parks` (with land use qualifier) | Parks as land use designation differ from parks as facility locations | Include `Park.*Land Use`, `Open Space.*Designation`, `Parks.*Zoning`; exclude standalone facility location layers |
| `Fire Stations` / `Police Stations` | Civic facility locations — not planning layers | Include only when in a planning service as community facilities reference; exclude as standalone operational layers |
| `Schools` (point locations) | School locations vs. school district boundaries | Include school district/catchment/attendance zone boundaries (Cluster G); exclude point facility locations unless in planning service |
| `Transit Stops` / `Transit Nodes` | Could be transit agency data or planning TOD overlay | Include when name references planning context (`Transit.*Priority`, `TOD.*Area`, `Transit.*Buffer`); flag standalone stop locations |
| `Voting Districts` / `Precincts` | Election administration vs. planning reference geography | Include as administrative reference layer (Cluster G) when co-located with planning layers; low standalone confidence |

---

## 6. URL Structure Patterns for Planning Services

### ArcGIS Online (Hosted Services) — Flat Structure
```
https://services[N].arcgis.com/[OrgID]/ArcGIS/rest/services/[ServiceName]/FeatureServer/[LayerIndex]
```
In AGOL orgs, each FeatureServer is individually named with no folder grouping. The service name IS effectively the layer name for Tier 1 matching purposes.

Planning-indicative service name patterns:
- Exact: `ComDev`, `Zoning`, `ZONING`, `Historic_District`, `Subdivisions`, `Parcels`, `TIF_Zones`, `Urban_Growth_Boundary`, `Specific_Plans`, `Opportunity_Sites`
- Contains: `Land_Use`, `MasterPlan`, `Plan`, `Agreement`, `Zoning`, `PLU`, `Housing`, `Development`, `Parcel`, `Historic`
- Suffix patterns: `_View` or `_ws` or `_SHP` appended to a planning term (e.g., `Residential_Zoning_View`, `CLV_ShortTermRental_ws`, `Milpitas_ZCU___Admin_Draft_Zoning_Map_V2_WFL1`)

### On-Premises / Self-Hosted ArcGIS Server — Folder Structure
```
https://gis.[jurisdiction].org/[server]/rest/services/[ServiceGroup]/[ServiceName]/MapServer/[LayerIndex]
```
Planning-indicative service group tokens: `EnerGov`, `ComDev`, `CDD`, `Planning`, `LandDev`, `CommunityDevelopment`, `CD`, `P_D` (Planning & Development)

When the ServiceGroup matches, ALL child services are presumptively planning-relevant (+5 base score before layer name evaluation).

### Single-Service County MapServers
```
https://gis.[county].[state].us/arcgis/rest/services/[GenericServiceName]/MapServer/[LayerIndex]
```
Common in counties under 150k population. The service name will be generic (`Website_Map_CityView`, `County_Parcels`, `PublicMap`, `PropertySearch`). No Tier 1 signal fires. Apply full Tier 2 keyword clustering to all layer names. Treat any layer scoring ≥ 2 as a candidate for planning inclusion and flag for human review.

### EnerGov Platform (Tyler Technologies)
The service name `EnerGov` in a `MapServer` endpoint identifies a Tyler Technologies permitting and land management platform. All layers within an EnerGov service have high planning/community development relevance: parcels, zoning, subdivision, permits, special use.

---

## 7. Named Abbreviations and Acronyms Reference

| Abbreviation | Meaning | Planning Relevance |
|-------------|---------|-------------------|
| `ComDev` | Community Development | Department name — highest confidence |
| `CDD` | Community Development Department | Department folder — California common; Tier 1 equivalent to ComDev |
| `PLU` | Planned Land Use | Zoning/general plan layer |
| `UGB` | Urban Growth Boundary | Comprehensive planning tool |
| `TDR` | Transfer of Development Rights | Density bonus mechanism |
| `TIF` | Tax Increment Financing | Economic/redevelopment planning |
| `ESA` | Environmentally Sensitive Area | Environmental overlay in land use code |
| `NRHP` | National Register of Historic Places | Historic preservation planning |
| `ROIS` | Regional/parcel overlay index (jurisdiction-specific) | Planning cross-reference system |
| `PID` | Parcel ID | Cadastral key — planning reference |
| `EnerGov` | Tyler Technologies permitting platform | Planning/CD department platform |
| `PACE` | Property Assessed Clean Energy | Agreement-based land use program |
| `DTMasterPlan` | Downtown Master Plan | Downtown planning district |
| `ZCU` | Zoning Code Update | Active regulatory update layer |
| `BMR` | Below Market Rate | Affordable housing program layer — California housing policy |
| `CFD` | Community Facilities District | Mello-Roos; tied to planned development approvals — California |
| `HQTC` | High Quality Transit Corridor | California AB 2923 housing law planning overlay |
| `SOI` | Sphere of Influence | LAFCO urban growth boundary — California |
| `RHNA` | Regional Housing Needs Allocation | California housing element statutory quota |
| `VAD` | Voluntary Agricultural District | NC/Southeast land use protection mechanism |
| `ETJ` | Extraterritorial Jurisdiction | Southeast/Texas planning and annexation boundary |
| `UDO` | Unified Development Ordinance | Southeast integrated zoning/subdivision code |
| `FLUM` | Future Land Use Map | Comprehensive Plan map — Southeast/Midwest common |
| `PUD` | Planned Unit Development | Development entitlement type — national |
| `SUP` | Special Use Permit | Conditional use entitlement — national |
| `TND` | Traditional Neighborhood Development | New Urbanist zoning type — Southeast/Midwest |
| `NMU` | Neighborhood Mixed Use | Zoning district type |
| `CBD` | Central Business District | Downtown zoning designation |

---

## 8. Confidence Scoring Model

Use this scoring rubric to rank candidate layers.

| Signal | Points |
|--------|--------|
| Tier 1: URL service path is `ComDev`, `CDD`, `EnerGov`, `Planning`, or exact department name | +5 |
| Tier 1: URL service path contains `Zoning`, `Land_Use`, `MasterPlan`, `Historic`, `Subdivision`, `TIF`, `PLU`, `HousingElement`, `Specific_Plans`, `Opportunity_Sites`, `Urban_Growth` | +4 |
| Tier 1: URL service path contains `Development`, `Agreement`, `Growth`, `Plan`, `LandDev`, `ZCU`, `FLUM` | +3 |
| Tier 2: Layer name contains 3+ keywords from a single semantic cluster (A–I) | +3 |
| Tier 2: Layer name contains 1–2 keywords from clusters A–F | +2 |
| Tier 2: Layer name matches Cluster I (Hazards/Development Restrictions) — standalone | +2 |
| Tier 2: Layer name contains administrative geography keyword (Cluster G) | +1 |
| Tier 2: Layer name matches Cluster J (Landmarks/Civic Features) — supporting only, requires co-occurring Tier 1 or Tier 2 signal | +1 |
| Exclusion: URL service path matches Public Works, Fire, Utilities, or Business License token | -5 |
| Exclusion: Layer name matches business license type (alcohol, gaming, massage, etc.) | -4 |
| Exclusion: Layer name matches utility infrastructure (sewer, water main, hydrant, etc.) | -3 |

**Interpretation:**
- Score ≥ 4: Include as planning layer (high confidence)
- Score 2–3: Include as likely planning layer (moderate confidence, flag for review)
- Score 0–1: Ambiguous — apply Cluster co-occurrence test
- Score ≤ -1: Exclude

---

## 9. Representative Layer Examples from Source Data

### Confirmed Planning Layers (Score ≥ 4)

| Layer Name | Service Name | Jurisdiction | Reason |
|-----------|-------------|-------------|--------|
| Zoning | `ComDev` | Aspen CO | Tier 1 department name + core planning content |
| Zone Overlay | `ComDev` | Aspen CO | Tier 1 + zoning overlay |
| Civic Master Plan | `ComDev` | Aspen CO | Tier 1 + Cluster C |
| Historic Districts | `ComDev` | Aspen CO | Tier 1 + Cluster D |
| TDR Sending Site | `ComDev` | Aspen CO | Tier 1 + TDR acronym |
| UGB | `ComDev` | Aspen CO | Tier 1 + UGB acronym |
| Future Land Use | `Future_Land_Use_2012` | Las Vegas NV | Tier 1 + Cluster A |
| General Plan Future Land Use | `CLV_PLU` | Las Vegas NV | Tier 1 PLU + Cluster A + C |
| Development Agreement Areas | `Development_Agreement_Areas` | Clark County NV | Tier 1 + Cluster B |
| Subdivisions | `EnerGov` | Grand Prairie TX | Tier 1 platform + Cluster B |
| Special Use Permit | `EnerGov` | Grand Prairie TX | Tier 1 platform + Cluster B |
| Zoning Planned Development | `EnerGov` | Grand Prairie TX | Tier 1 platform + Cluster A |
| Historic District | `Historic_District` | Dublin OH | Tier 1 + Cluster D |
| NRHP Boundary | `NRHP_Boundary` | Dublin OH | Tier 1 + Cluster D |
| TIF Parcels | `TIF_Parcels` | Dublin OH | Tier 1 + Cluster F + B |
| Special Area Plans | `Special_Area_Plan` | Dublin OH | Tier 1 + Cluster C |
| Master Planned Communities | `Master_Planned_Communities_View` | Clark County NV | Tier 1 + Cluster C |
| Form-Based Code Prohibited Area | `General_Plan_Future_Land_Use` | Las Vegas NV | Tier 1 + regulatory land use |
| Residential Zoning | `Residential_Zoning_View` | Las Vegas NV | Tier 1 + Cluster A |
| Annex Pending | `ComDev` | Aspen CO | Tier 1 + annexation = planning action |
| ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A — exact match; single-service county MapServer |
| MUNICIPAL ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A |
| COUNTY ZONING | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster A |
| MOUNT AIRY HISTORIC DISTRICT | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster D — exact match |
| VOLUNTARY AGRICULTURAL DISTRICTS | `Website_Map_CityView` | Surry County NC | Tier 2 Cluster B — VAD is a land use protection mechanism |
| Parcels | `CDD/HousingElement` | Sunnyvale CA | Tier 1 CDD folder + Cluster F |
| Housing Element Sites (By-Right) | `CDD/HousingElement` | Sunnyvale CA | Tier 1 CDD + Cluster B — California statutory planning document |
| SpecificPlans | `CDD/HousingElement` | Sunnyvale CA | Tier 1 CDD + Cluster C |
| Assessor Parcels | `services8.arcgis.com/OPmRdssd8jj0bT5H` | Milpitas CA | Tier 1 `Assessor.*Parcel` + Cluster F |
| Milpitas_ZCU___Admin_Draft_Zoning_Map | AGOL flat service | Milpitas CA | Tier 1 `Zoning` + ZCU acronym |
| Land Use Overlay Exception | AGOL flat service | Milpitas CA | Tier 1 `Land_Use` + `Overlay` |
| Planned Unit Development | AGOL flat service | Milpitas CA | Tier 1 pattern + Cluster A |
| Specific Plans | AGOL flat service | Milpitas CA | Tier 1 `Specific_Plans` pattern + Cluster C |
| Urban Growth Boundary | AGOL flat service | Milpitas CA | Tier 1 `UGB`/`Growth` exact + Cluster C |
| Zoning By Parcel | AGOL flat service | Milpitas CA | Tier 1 `Zoning` + Cluster F |
| Zoning Overlay Exception | AGOL flat service | Milpitas CA | Tier 1 `Zoning` + `Overlay` |
| Sphere of Influence | AGOL flat service | Milpitas CA | Cluster C — LAFCO urban growth boundary |
| Milpitas Historical Inventory | AGOL flat service | Milpitas CA | Cluster D — historic resource survey |
| Hillside Building Code | AGOL flat service | Milpitas CA | Cluster A — hillside zoning regulation |
| Flood Zone Parcels | AGOL flat service | Milpitas CA | Cluster E + F — flood overlay + parcel cross-reference |
| Community_Development_Spatial_Rules_Test | AGOL flat service | Milpitas CA | Tier 1 equivalent — `Community_Development` in service name |
| Transit_Priority_Areas_and_HQTC | AGOL flat service | Milpitas CA | Cluster C — California housing law planning overlay |

### Excluded Layers (Score ≤ -1)

| Layer Name | Service Name | Jurisdiction | Reason |
|-----------|-------------|-------------|--------|
| Gaming Restricted (1-5 Slots) | `LIVE_CLV_BUS` | Las Vegas NV | Business license record |
| Alcohol On-Premise Full | `LIVE_CLV_BUS` | Las Vegas NV | Business license record |
| Massage Establishment | `LIVE_CLV_BUS` | Las Vegas NV | Business license record |
| Phantoms - Fire Map | `FD_PHANTOMS_View` | Las Vegas NV | Fire department operational layer |
| PW Bike Trails Status | `PW_Bike_Trails_Existing_Proposed` | Clark County NV | Public Works infrastructure |
| Streets / Major Streets | `SCL` / `LIVE_SCL_Majors` | Las Vegas NV | Transportation infrastructure |
| CCSD Schools | `CCSD_Schools_Protected_Use` | Clark County NV | School district — not planning dept |
| Alcohol Beverage Control License | AGOL flat service | Milpitas CA | Business license record |
| Business_License_Public_View | AGOL flat service | Milpitas CA | Business license record |
| Fire Stations / Fire Run Pathways | AGOL flat service | Milpitas CA | Fire department operational layers |
| Pavement Condition / Pavement Index | AGOL flat service | Milpitas CA | Public Works asset management |
| Police Beats / Police_Traffic_Citations | AGOL flat service | Milpitas CA | Law enforcement operational layers |
| Water Hydrant / Water Meter | AGOL flat service | Milpitas CA | Utility infrastructure |
| Sanitary_Sewer_Basins | AGOL flat service | Milpitas CA | Utility infrastructure |
| Street Sweeping Routes | AGOL flat service | Milpitas CA | Public Works operations |
| AIRPORTS | `Website_Map_CityView` | Surry County NC | Transportation infrastructure |
| FIRE HYDRANTS / FIRE WATER POINTS | `Website_Map_CityView` | Surry County NC | Fire/utility infrastructure |
| ROADS / RAILROADS | `Website_Map_CityView` | Surry County NC | Transportation infrastructure |
Imagery / Aerial imagery / basemaps


---

## 10. Regional Terminology Reference

This section documents planning terminology that varies by U.S. region. Use in conjunction with Tier 2 clusters when matching layers from unfamiliar jurisdictions.

### California
California has a statutory planning framework that produces distinctive layer naming:

| Term | Meaning | Cluster |
|------|---------|---------|
| `Housing Element` | Mandatory General Plan element governing housing supply | B, C |
| `RHNA` / `RHNA Sites` / `RHNA Allocation` | Regional Housing Needs Allocation — statutory housing unit quota; layers track rezoning compliance and candidate sites | B |
| `Specific Plan` / `Precise Plan` | Subarea regulatory plan (similar to Special Area Plan) | C |
| `Sphere of Influence (SOI)` | LAFCO-designated urban growth boundary | C, G |
| `HQTC` / `High Quality Transit Corridor` | AB 2923 transit-oriented overlay for housing; also triggers SB 9 and density bonus applicability | C |
| `Transit Priority Area` | Half-mile buffer around major transit stops — housing law trigger | C |
| `SB 9 Overlay` / `AB 2923 Zone` | State law overlays enabling ministerial two-unit development and lot splits; planning departments map these to show applicability areas | A, B |
| `Two-Unit Overlay` / `Lot Split Zone` | Alternate naming for SB 9 applicability layers | A, B |
| `State Density Bonus` / `Ministerial Zone` | Areas subject to state-mandated density bonus or ministerial approval | A, B |
| `ADU.*Overlay` / `ADU.*Zone` / `Accessory Dwelling` / `Junior ADU` | Accessory Dwelling Unit applicability or restriction zones — planning-administered | A, B |
| `BMR` / `Below Market Rate` | Affordable housing program tied to development approvals | B |
| `CFD` / `CFD Parcels` | Community Facilities District — Mello-Roos financing tied to planned development | B, F |
| `Mello-Roos` / `Mello_Roos` / `MelloRoos` | Standalone Mello-Roos district boundary — GIS admins frequently use this name rather than CFD | B, F |
| `Hillside Building Code` | Local zoning overlay for hillside development standards | A |
| `City Boundary Adjustment` | Annexation/SOI action — planning boundary change | B, G |
| `CEQA.*Overlay` | California Environmental Quality Act review zones | E |
| `Density Bonus` | State-mandated affordability bonus zones | B |

### Southeast (NC, SC, GA, FL, TN, AL, MS, VA)
Southeast planning departments use Dillon's Rule and county-level planning more heavily:

| Term | Meaning | Cluster |
|------|---------|---------|
| `UDO` / `Unified Development Ordinance` | Integrated zoning + subdivision code (replaces separate zoning ordinance) | A |
| `ETJ` / `Extraterritorial Jurisdiction` | Planning authority beyond city limits — NC statutory, TX statutory | G |
| `Voluntary Agricultural District (VAD)` | NC/VA land use protection program for farmland | B |
| `FLUM` / `Future Land Use Map` | Comprehensive Plan map layer | A, C |
| `Comprehensive Plan` | Southeast/Midwest equivalent of General Plan | C |
| `Sector Plan` | Subarea comprehensive plan — common in GA, FL | C |
| `Corridor Plan` | Linear subarea plan (roads/transit corridors) | C |
| `Small Area Plan` | Neighborhood-level planning document | C |
| `Conservation Subdivision` | Cluster development with open space preservation | B |
| `TND` / `Traditional Neighborhood Development` | New Urbanist zoning type — common in FL, NC | A |
| `Rural Preservation District` | Agricultural land use protection district | A, B |
| `Activity Center` | Mixed-use growth node designation | C |
| `NPDES.*Buffer` | Riparian buffer zone — planning-regulated in NC/SE | E |
| `Flood.*Administration` | Floodplain management — in Southeast, often a planning function | E |

### Midwest (OH, IN, IL, MI, WI, MN, IA, MO)
Midwest planning is often township-based with county and municipal layers coexisting:

| Term | Meaning | Cluster |
|------|---------|---------|
| `Comprehensive Plan` | Equivalent of General Plan | C |
| `FLUM` | Future Land Use Map from Comprehensive Plan | A, C |
| `Township` | Civil township boundary — Midwest land survey unit; planning reference | G |
| `TIF District` | Tax Increment Financing district — redevelopment planning | B |
| `Corridor Plan` | Linear subarea planning document | C |
| `Conservation District` | Land use overlay for agricultural/environmental protection | A, E |
| `Special Assessment District` | Infrastructure financing tied to development | B |
| `UDO` | Unified Development Ordinance — increasingly common | A |
| `Planned Unit Development (PUD)` | Entitlement type | B |
| `Overlay District` | Zoning overlay — flood, historic, airport, etc. | A |
| `Enterprise Zone` | Economic development overlay — planning/community dev | B |
| `Tax Abatement.*Parcel` | Redevelopment incentive — planning/community dev | F |
| `Annexation.*Boundary` | Municipal growth boundary action | B, G |
| `Section.*Township.*Range` | PLSS (Public Land Survey System) grid — Midwest cadastral reference | F |

### Southwest / Mountain West (AZ, NM, CO, NV, UT, ID, WY, MT)
Large county footprints, tribal land overlaps, and water rights create distinctive layer patterns:

| Term | Meaning | Cluster |
|------|---------|---------|
| `General Plan` | State planning document (AZ, NV, UT use this term) | C |
| `PAD` / `Planned Area Development` | Arizona equivalent of PUD/Specific Plan | B, C |
| `Specific Plan` | AZ/NM subarea plan | C |
| `Rural Planning Area` | Unincorporated county planning designation | C |
| `View Corridor` / `Viewshed` | Scenic protection overlay | C, E |
| `Floodplain.*Zone` | FEMA flood designation — planning/zoning regulated in West | E |
| `Water Rights.*Overlay` | Land use constraint related to water availability | E |
| `Wildfire Hazard` / `WUI` (Wildland-Urban Interface) | Planning-regulated overlay | E |
| `Dark Sky.*Overlay` | Outdoor lighting code overlay | H |
| `Tribal.*Boundary` / `Tribal.*Land` | Tribal jurisdiction — planning context boundary | G |
| `Military.*Influence.*Area` | JLUS (Joint Land Use Study) overlay — planning regulated | H |

### Texas
Texas has unique planning law (Dillon's Rule + home rule + ETJ):

| Term | Meaning | Cluster |
|------|---------|---------|
| `ETJ` | Extraterritorial Jurisdiction — up to 5 miles beyond city limits | G |
| `PDD` / `Planned Development District` | Texas equivalent of PUD/Specific Plan | B |
| `SUP` / `Specific Use Permit` | Texas conditional use entitlement | B |
| `Thoroughfare Plan` | Road network plan — planning department function in TX | C |
| `Reinvestment Zone` | Tax increment financing zone (TIRZ) | B |
| `TIRZ` | Tax Increment Reinvestment Zone | B |
| `4B Sales Tax.*District` | Economic development district — community dev function | B |
| `Annexation.*Schedule` | City annexation plan | B, G |

---

*Analysis based on 300+ layers from 7 municipal/county ArcGIS environments: City of Aspen CO (ComDev), City of Grand Prairie TX (EnerGov), City of Dublin OH, Clark County / City of Las Vegas NV, Surry County NC, City of Sunnyvale CA (CDD), and City of Milpitas CA (ArcGIS Online).*  
*Version 2.0 updates: Added CDD/Planning/LandDev Tier 1 tokens; California statutory terminology (Housing Element, Precise Plan, SOI, HQTC, BMR, CFD, ZCU); Southeast terminology (VAD, ETJ, UDO, FLUM, Sector Plan); Midwest terminology (Township, TIF District, Section-Township-Range); Southwest/Mountain West (PAD, WUI, Dark Sky); Texas (ETJ, TIRZ, PDD); ArcGIS Online flat-structure pattern; Single-service county MapServer structural note; expanded Exclusion signals for Utilities and Police; 10 new Ambiguous layer entries; expanded Abbreviations table.*  
*Version 2.1 updates: Added RHNA layer name patterns to Tier 2 Cluster B and California table; added SB 9/AB 2923 overlay zone keywords to Tier 2 Cluster A and California table; added Mello-Roos standalone Tier 1 token to Parcel and Property Services; added ADU/Accessory Dwelling Unit keywords to Tier 2 Cluster A and California table; expanded California table entries to include layer naming guidance for each term.*  
*Version 2.2 updates: Expanded Cluster E with full flood hazard variant vocabulary (Floodplain, Floodway, 100/500 Year Flood, FEMA Floodplain, SFHA) and geologic/fire hazard terms (Earthquake Zone, Seismic Hazard, Tsunami Zone, Steep Slopes, Wildfire District/Zone); expanded Cluster G to full Administrative Boundaries coverage (Municipalities, Counties, ZIP Codes, Voting Districts, School Catchments); added Cluster I: Hazards and Development Restrictions (comprehensive flood, fire, geologic, wetland, riparian, agricultural, easement, and contour variants); added Cluster J: Landmarks and Civic Features (schools, parks, transit, civic buildings, water features, recreation facilities) with supporting-only scoring rule; added 14 new Ambiguous layer entries; updated scoring model to reference Clusters I and J.*
