# BhumiSetu Geospatial & GIS Architecture

## 1. Coordinate Reference Systems (CRS)
- **Storage & Ingestion**: `WGS84` (`EPSG:4326`) for GPS points, lat/long pins, and GeoJSON interchange.
- **Projected Computation**: `UTM Zone 45N` (`EPSG:32645`) for Jharkhand/Bihar planar calculations, ensuring sub-centimeter geodesic accuracy for parcel areas.

## 2. Spatial Math & Delta Formulas

### Shoelace Polygon Geodesic Area
$$\text{Area} = \frac{1}{2} \left| \sum_{i=0}^{n-1} (x_i y_{i+1} - x_{i+1} y_i) \right|$$

### Area Discrepancy Percentage
$$\Delta_{\text{area}}\% = \frac{\text{Measured Ground Area} - \text{Recorded Document Area}}{\text{Recorded Document Area}} \times 100$$

### Discrepancy Thresholds
- $|\Delta_{\text{area}}| \le 2.0\%$: Normal agrarian measurement tolerance.
- $2.0\% < |\Delta_{\text{area}}| \le 5.0\%$: Minor boundary shift or ridge erosion.
- $|\Delta_{\text{area}}| > 5.0\%$: Critical Encroachment or Shortfall Flag $\rightarrow$ Triggers mandatory on-ground Chauhadri audit.

## 3. Indic Regional Land Conversion Standards
- **1 Acre** = 100 Decimals = 32 Kathas = 640 Dhurs = 43,560 Sq.Ft = 4,046.86 Sq.M = 0.4047 Hectares.
- **1 Katha** (Deoghar Standard / 4-Haath Laggi) = 20 Dhurs = 3.125 Decimals = 1,361.25 Sq.Ft.
- **1 Bigha** (Standard) = 20 Kathas = 27,225 Sq.Ft = 0.625 Acres.
