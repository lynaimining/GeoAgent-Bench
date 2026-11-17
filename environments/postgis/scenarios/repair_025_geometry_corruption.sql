-- Pre-seeded artifact for repair_025: correct attributes for every active school,
-- but geometries for schools 3 and 9 are taken from the stale 2019 archive
-- (they moved since then) instead of the current locations. Attributes are
-- otherwise entirely correct, so the corruption is invisible unless checked spatially.
CREATE TABLE school_locations_broken AS
SELECT s.school_id, s.name, s.status, s.enrollment,
       COALESCE(a.geom, s.geom) AS geom
FROM schools_current s
LEFT JOIN schools_2019_archive a ON a.school_id = s.school_id AND s.school_id IN (3, 9)
WHERE s.status = 'active';
