"""Example adapter for G200-04-S01. Build and read back a PostGIS result."""

import json
import os
from pathlib import Path

import psycopg2

SQL = """
CREATE TABLE public.flood_risk_schools AS
SELECT s.school_id, s.name, s.geom
FROM public.schools_current s
WHERE s.status = 'active'
  AND EXISTS (
    SELECT 1 FROM public.rivers r
    WHERE r.name = 'Main River' AND ST_DWithin(s.geom, r.geom, 500)
  );
"""


def main():
    if os.environ["BENCH_TASK_ID"] != "G200-04-S01":
        raise ValueError("This example is specific to G200-04-S01")
    output = Path(os.environ["BENCH_OUTPUT_DIR"])
    with psycopg2.connect(os.environ["BENCH_DB_DSN"]) as conn, conn.cursor() as cur:
        cur.execute(SQL)
        cur.execute("SELECT count(*), min(ST_SRID(geom)), max(ST_SRID(geom)) FROM public.flood_risk_schools")
        count, srid_min, srid_max = cur.fetchone()
    (output / "query.sql").write_text(SQL, encoding="utf-8")
    (output / "result.json").write_text(json.dumps({
        "status": "completed",
        "summary": "Saved and read back public.flood_risk_schools.",
        "metrics": [{"name": "school_count", "value": count, "unit": "rows"}],
        "artifacts": [{"path": "query.sql", "readback": "Executed SQL saved to output"}],
        "evidence": [{"detail": f"PostGIS read back {count} rows with SRID range {srid_min}..{srid_max}.",
                      "tool": "PostGIS ST_DWithin", "parameters": {"distance_m": 500, "status": "active"}}],
        "limitations": ["Synthetic city example"],
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
