-- Pre-seeded artifact for audit_024 with TWO simultaneous, independent defects:
-- (1) wrong_filter: no status filter, so closed schools (12, 17) are included;
-- (2) duplicate_rows: joins school_addresses without an is_primary filter, so
--     schools with duplicate address rows (2, 5, 15) appear more than once.
CREATE TABLE school_directory_broken AS
SELECT s.school_id, s.name, s.enrollment, a.address
FROM schools_current s
JOIN school_addresses a ON a.school_id = s.school_id;
