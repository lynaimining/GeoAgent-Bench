# Data Dictionary — my_world_v0 (rename me!)
CRS: EPSG:32643 (metric, metres). Extent: 10 km x 8 km.

| Layer | Geometry | Key columns |
|---|---|---|
| rivers | LineString | river_id, name, type |
| wards | Polygon | ward_id, name, population, avg_elevation_m |
| roads | LineString | road_id, name, road_class |
| schools_current | Point | school_id, name, status, enrollment |
| schools_2019_archive | Point | school_id, name, status, enrollment_2019 (STALE - trap layer) |
| hospitals | Point | hospital_id, name, beds |
| metro_stations | Point | station_id, name, daily_ridership |
| school_addresses | (none) | school_id, address, is_primary (contains duplicates) |
