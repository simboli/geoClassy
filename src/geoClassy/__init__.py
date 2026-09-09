"""Label GPS points with the OpenStreetMap area that contains them.

    >>> import geoClassy
    >>> areas = geoClassy.load("nyc-neighborhoods.geojson")
    >>> areas.locate(40.748417, -73.985833)
    'Midtown South'

The 0.1.x function API still lives in :mod:`geoClassy.single`, deprecated and
scheduled for removal in 1.0.
"""

from ._core import (
    Areas,
    GeoClassyError,
    InvalidGeoJSONError,
    NoAreasFoundError,
    OverlapError,
    load,
)

__version__ = "0.2.1"

__all__ = [
    "Areas",
    "load",
    "GeoClassyError",
    "InvalidGeoJSONError",
    "NoAreasFoundError",
    "OverlapError",
    "__version__",
]
