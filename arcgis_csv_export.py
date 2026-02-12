#!/usr/bin/env python3
"""
ArcGIS Feature Service to CSV Exporter

Retrieves all records from an Esri ArcGIS Feature Service endpoint
and exports them to a CSV file.

Usage:
    python arcgis_csv_export.py <feature_service_url> [--output OUTPUT_FILE]

Example:
    python arcgis_csv_export.py "https://sampleserver6.arcgisonline.com/arcgis/rest/services/Census/MapServer/3"
    python arcgis_csv_export.py "https://services.arcgis.com/org123/arcgis/rest/services/MyService/FeatureServer/0" --output my_data.csv
"""

import argparse
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def make_request(url, params=None, max_retries=3):
    """Make an HTTP GET request with retry logic."""
    if params:
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
    else:
        full_url = url

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(full_url, headers={
                "User-Agent": "ArcGIS-CSV-Exporter/1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Request failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Request failed after {max_retries} attempts: {e}"
                ) from e


def get_layer_metadata(base_url):
    """Fetch layer metadata including fields and maxRecordCount."""
    print(f"Fetching layer metadata from:\n  {base_url}")
    metadata = make_request(base_url, {"f": "json"})

    if "error" in metadata:
        code = metadata["error"].get("code", "")
        msg = metadata["error"].get("message", "Unknown error")
        raise RuntimeError(f"ArcGIS API error {code}: {msg}")

    return metadata


def get_total_count(base_url):
    """Get the total number of records in the layer."""
    result = make_request(base_url + "/query", {
        "where": "1=1",
        "returnCountOnly": "true",
        "f": "json",
    })
    if "error" in result:
        raise RuntimeError(f"Count query failed: {result['error']}")
    return result.get("count", 0)


def get_all_object_ids(base_url):
    """Retrieve all object IDs from the layer."""
    result = make_request(base_url + "/query", {
        "where": "1=1",
        "returnIdsOnly": "true",
        "f": "json",
    })
    if "error" in result:
        raise RuntimeError(f"OID query failed: {result['error']}")

    oid_field = result.get("objectIdFieldName", "OBJECTID")
    oids = sorted(result.get("objectIds", []))
    return oid_field, oids


def fetch_features_paginated(base_url, max_record_count):
    """Fetch all features using resultOffset pagination."""
    all_features = []
    offset = 0

    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": max_record_count,
        }
        result = make_request(base_url + "/query", params)

        if "error" in result:
            raise RuntimeError(f"Query failed at offset {offset}: {result['error']}")

        features = result.get("features", [])
        all_features.extend(features)
        print(f"  Fetched {len(all_features)} records so far...")

        if not result.get("exceededTransferLimit", False):
            break

        offset += max_record_count

    return all_features


def fetch_features_by_oids(base_url, oid_field, oids, batch_size):
    """Fetch all features by batching object IDs (fallback method)."""
    all_features = []

    for i in range(0, len(oids), batch_size):
        batch = oids[i : i + batch_size]
        params = {
            "objectIds": ",".join(str(oid) for oid in batch),
            "outFields": "*",
            "returnGeometry": "true",
            "f": "json",
        }
        result = make_request(base_url + "/query", params)

        if "error" in result:
            raise RuntimeError(
                f"OID batch query failed (batch starting at index {i}): "
                f"{result['error']}"
            )

        features = result.get("features", [])
        all_features.extend(features)
        print(f"  Fetched {len(all_features)} records so far...")

    return all_features


def format_field_value(value, field_type):
    """Format a field value based on its ArcGIS field type."""
    if value is None:
        return ""
    if field_type in ("esriFieldTypeDate",):
        try:
            dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (OSError, ValueError, TypeError):
            return str(value)
    return value


def geometry_to_string(geometry):
    """Convert an ArcGIS geometry object to a readable string."""
    if geometry is None:
        return ""

    # Point
    if "x" in geometry and "y" in geometry:
        x, y = geometry["x"], geometry["y"]
        if x == "NaN" or y == "NaN":
            return ""
        return f"POINT ({x} {y})"

    # Polyline
    if "paths" in geometry:
        parts = []
        for path in geometry["paths"]:
            coords = ", ".join(f"{p[0]} {p[1]}" for p in path)
            parts.append(f"({coords})")
        return f"MULTILINESTRING ({', '.join(parts)})"

    # Polygon
    if "rings" in geometry:
        parts = []
        for ring in geometry["rings"]:
            coords = ", ".join(f"{p[0]} {p[1]}" for p in ring)
            parts.append(f"({coords})")
        return f"POLYGON ({', '.join(parts)})"

    # Multipoint
    if "points" in geometry:
        coords = ", ".join(f"({p[0]} {p[1]})" for p in geometry["points"])
        return f"MULTIPOINT ({coords})"

    # Fallback: return JSON
    return json.dumps(geometry)


def normalize_url(url):
    """Clean up the input URL, stripping trailing slashes and query strings."""
    url = url.strip().rstrip("/")
    # Remove any existing query string
    url = url.split("?")[0]
    # Remove trailing /query if present
    if url.endswith("/query"):
        url = url[: -len("/query")]
    return url


def build_field_map(fields):
    """Build a dict of field_name -> field_type from metadata fields."""
    return {f["name"]: f.get("type", "") for f in fields}


def export_to_csv(features, fields, geometry_type, output_path):
    """Write features to a CSV file."""
    field_map = build_field_map(fields)
    field_names = [f["name"] for f in fields]
    has_geometry = geometry_type is not None and geometry_type != ""

    headers = list(field_names)
    if has_geometry:
        headers.append("GEOMETRY")

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for feature in features:
            attrs = feature.get("attributes", {})
            row = []
            for name in field_names:
                raw = attrs.get(name)
                ftype = field_map.get(name, "")
                row.append(format_field_value(raw, ftype))

            if has_geometry:
                row.append(geometry_to_string(feature.get("geometry")))

            writer.writerow(row)

    return len(features)


def generate_output_filename(metadata):
    """Generate a default output filename from the layer name."""
    name = metadata.get("name", "arcgis_export")
    # Sanitize for use as a filename
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name)
    safe_name = safe_name.strip().replace(" ", "_")
    return f"{safe_name}.csv"


def main():
    parser = argparse.ArgumentParser(
        description="Export all records from an ArcGIS Feature Service to CSV.",
        epilog=(
            "Example:\n"
            '  python arcgis_csv_export.py "https://sampleserver6.arcgisonline.com'
            '/arcgis/rest/services/Census/MapServer/3"\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        help="ArcGIS Feature/Map Service layer URL (e.g. .../FeatureServer/0)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV file path (default: derived from layer name)",
    )
    args = parser.parse_args()

    base_url = normalize_url(args.url)
    print(f"\nArcGIS Feature Service CSV Exporter")
    print(f"{'=' * 40}")

    # Step 1: Get layer metadata
    metadata = get_layer_metadata(base_url)
    layer_name = metadata.get("name", "Unknown")
    geometry_type = metadata.get("geometryType")
    max_record_count = metadata.get("maxRecordCount", 1000)
    fields = metadata.get("fields", [])

    if not fields:
        print("Error: No fields found in layer metadata.", file=sys.stderr)
        sys.exit(1)

    supports_pagination = (
        metadata.get("advancedQueryCapabilities", {})
        .get("supportsPagination", False)
    )

    print(f"\nLayer name:         {layer_name}")
    print(f"Geometry type:      {geometry_type or 'None (table)'}")
    print(f"Fields:             {len(fields)}")
    print(f"Max records/query:  {max_record_count}")
    print(f"Supports pagination: {supports_pagination}")

    # Step 2: Get total record count
    total_count = get_total_count(base_url)
    print(f"Total records:      {total_count}")

    if total_count == 0:
        print("\nNo records to export.")
        sys.exit(0)

    # Step 3: Fetch all features
    print(f"\nDownloading records...")
    if supports_pagination:
        features = fetch_features_paginated(base_url, max_record_count)
    else:
        print("  Pagination not supported, using Object ID batching...")
        oid_field, oids = get_all_object_ids(base_url)
        features = fetch_features_by_oids(base_url, oid_field, oids, max_record_count)

    print(f"\nTotal features retrieved: {len(features)}")

    # Step 4: Export to CSV
    output_path = args.output or generate_output_filename(metadata)
    print(f"Writing CSV to: {output_path}")
    row_count = export_to_csv(features, fields, geometry_type, output_path)
    print(f"Exported {row_count} records to {output_path}")
    print("Done.")


if __name__ == "__main__":
    main()
