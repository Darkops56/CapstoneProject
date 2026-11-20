"""Configuration constants and WCAG 2.2 color palette definitions."""

# CABA Bounding Box limits
CABA_BBOX = {
    "lat_min": -34.71,
    "lat_max": -34.52,
    "lon_min": -58.54,
    "lon_max": -58.34,
}

# Standard Price Thresholds
PRICE_CUT_LOW_PCT = -5.0
PRICE_CUT_HIGH_PCT = 10.0

# WCAG 2.2 Accessible RGBA Colors [R, G, B, A]
COLOR_BAJO_PRECIO = [15, 118, 110, 210]   # Emerald Teal (#0F766E)
COLOR_PRECIO_JUSTO = [217, 119, 6, 210]   # Warm Amber (#D97706)
COLOR_SOBREPRECIO = [220, 38, 38, 210]   # Crimson Coral (#DC2626)
COLOR_DEFAULT = [100, 116, 139, 200]      # Slate (#64748B)

# Recommendation Colors
COLOR_ALTAMENTE_RECOMENDADA = [16, 185, 129, 220]  # Bright Green
COLOR_RECOMENDADA = [59, 130, 246, 210]            # Blue
COLOR_EVALUAR = [234, 179, 8, 210]                 # Yellow
COLOR_DESCARTAR = [239, 68, 68, 210]               # Red

PAGE_SIZE = 12
REQUEST_TIMEOUT_SECONDS = 10.0
CARTO_POSITRON_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"

# Crime HeatmapLayer WebGL parameters (ColorBrewer Reds progression)
CRIME_HEATMAP_COLOR_RANGE = [
    [255, 245, 240, 40],
    [254, 224, 210, 110],
    [252, 146, 114, 165],
    [251, 106, 74, 200],
    [222, 45, 38, 225],
    [165, 15, 21, 245],
]
CRIME_HEATMAP_RADIUS_PIXELS = 55
CRIME_HEATMAP_INTENSITY = 1.2
CRIME_HEATMAP_THRESHOLD = 0.05
CRIME_HEATMAP_OPACITY = 0.6
CRIME_HEATMAP_MAX_POINTS = 2000
SCATTER_STROKE_COLOR = [15, 23, 42, 210]
