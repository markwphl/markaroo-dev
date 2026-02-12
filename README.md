# ArcGIS Feature Service CSV Exporter

Exports all records from an Esri ArcGIS Feature Service (or Map Service) layer
endpoint to a `.csv` file using the free ArcGIS REST API.

## Requirements

- Python 3.6+
- No external dependencies (uses only the Python standard library)

## Usage

```bash
python arcgis_csv_export.py <feature_service_layer_url> [--output OUTPUT_FILE]
```

### Arguments

| Argument          | Description                                                      |
| ----------------- | ---------------------------------------------------------------- |
| `url`             | The ArcGIS Feature/Map Service layer URL (e.g. `.../FeatureServer/0`) |
| `--output`, `-o`  | Output CSV file path (default: derived from the layer name)      |

### Examples

```bash
# Export a Census layer from an Esri sample server
python arcgis_csv_export.py \
  "https://sampleserver6.arcgisonline.com/arcgis/rest/services/Census/MapServer/3"

# Specify an output filename
python arcgis_csv_export.py \
  "https://services.arcgis.com/org/arcgis/rest/services/MyData/FeatureServer/0" \
  --output my_data.csv
```

## How It Works

1. **Fetches layer metadata** from the service endpoint to discover field
   definitions, geometry type, and the server's `maxRecordCount` limit.
2. **Counts total records** via `returnCountOnly=true`.
3. **Downloads all features** by paginating with `resultOffset` /
   `resultRecordCount`. If the server does not support pagination, it falls
   back to Object ID-based batching (`returnIdsOnly` then `objectIds` queries).
4. **Writes a CSV** with all attribute fields plus a `GEOMETRY` column (WKT
   format) when spatial data is present. Date fields are converted from epoch
   milliseconds to `YYYY-MM-DD HH:MM:SS` (UTC).

## Supported Service Types

- ArcGIS Feature Server layers (`.../FeatureServer/<layer_id>`)
- ArcGIS Map Server layers (`.../MapServer/<layer_id>`)
- ArcGIS Online and ArcGIS Enterprise services
- Public (unauthenticated) endpoints
