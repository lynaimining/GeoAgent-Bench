"""Controller: recompute numeric references for the bundled mining fixtures.

From the repository root: python -m evaluator.synthetic_references
This command updates evaluator/references. Use a copy when experimenting.
"""

import csv
import math
import statistics as stats
from collections import Counter, defaultdict

from geoagent_bench.common import ROOT, read_json, write_json

BUNDLED = ROOT / "assets/bundled/data/synthetic"
MINING = BUNDLED / "mining"


def ref(name, value):
    write_json(ROOT / "evaluator/references" / f"{name}.json", value)


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [dict(row, row_number=i) for i, row in enumerate(csv.DictReader(stream), 1)]


def drill_tables(folder):
    return {
        kind: csv_rows(MINING / folder / filename)
        for kind, filename in (("collar", "01_collar.csv"), ("survey", "02_survey.csv"),
                               ("assay", "03_assay.csv"), ("litho", "04_litho.csv"))
    }


def finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def intervals(rows):
    valid, invalid, overlaps = defaultdict(list), [], []
    for row in rows:
        start, end = finite(row.get("from_m", row.get("from"))), finite(row.get("to_m", row.get("to")))
        if start is None or end is None or not 0 <= start < end:
            invalid.append(row)
            continue
        valid[row["hole_id"]].append((start, end, row))
    for hole, values in valid.items():
        values.sort(key=lambda x: (x[0], x[1], x[2]["row_number"]))
        for i, (a, b, row) in enumerate(values):
            for c, d, other in values[i+1:]:
                if c >= b:
                    break
                overlaps.append({
                    "hole_id": hole, "rows": [row["row_number"], other["row_number"]],
                    "overlap_length_m": min(b, d) - c, "exact_duplicate": (a, b) == (c, d),
                })
    return valid, invalid, overlaps


def coverage(valid, collars):
    result = []
    for collar in collars:
        hole = collar["hole_id"]
        depth = float(collar["max_depth"])
        merged, gaps, beyond = [], [], []
        for a, b, row in valid[hole]:
            if b > depth:
                beyond.append(row["row_number"])
            b = min(b, depth)
            if b > a:
                if merged and a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
        prev = 0.0
        for a, b in merged:
            if prev < a:
                gaps.append([prev, a])
            prev = b
        if prev < depth:
            gaps.append([prev, depth])
        length = sum(b-a for a, b in merged)
        result.append({"hole_id": hole, "max_depth_m": depth, "covered_m": length,
                       "coverage_fraction": length / depth, "gaps": gaps, "beyond_bottom_rows": beyond})
    return result


def delta(length, a, b):
    angle1, az1 = math.radians(90 + a[0]), math.radians(a[1])
    angle2, az2 = math.radians(90 + b[0]), math.radians(b[1])
    cosine = math.cos(angle1)*math.cos(angle2) + math.sin(angle1)*math.sin(angle2)*math.cos(az2-az1)
    dogleg = math.acos(max(-1, min(1, cosine)))
    scale = length / 2 if dogleg < 1e-10 else length * math.tan(dogleg / 2) / dogleg
    return (
        scale * (math.sin(angle1)*math.sin(az1) + math.sin(angle2)*math.sin(az2)),
        scale * (math.sin(angle1)*math.cos(az1) + math.sin(angle2)*math.cos(az2)),
        -scale * (math.cos(angle1) + math.cos(angle2)),
    )


def survey_references(collars, rows):
    stations, invalid = defaultdict(list), []
    for row in rows:
        md, dip, az = (finite(row[k]) for k in ("depth", "dip", "azimuth"))
        if None in (md, dip, az) or not (md >= 0 and -90 <= dip <= 90 and 0 <= az < 360):
            invalid.append(row)
        else:
            stations[row["hole_id"]].append((md, dip, az, row["row_number"]))
    duplicates, missing_zero, disorder = [], [], []
    trajectory, displacement, unresolved = [], [], []
    for hole, collar in collars.items():
        values = stations[hole]
        if not values:
            unresolved.append(hole)
            continue
        if any(a[0] > b[0] for a, b in zip(values, values[1:])):
            disorder.append(hole)
        values.sort()
        counts = Counter(v[0] for v in values)
        repeated = [d for d, n in counts.items() if n > 1]
        if repeated or len(collar) != 1:
            duplicates.extend({"hole_id": hole, "depth": d, "rows": [v[3] for v in values if v[0] == d]}
                              for d in repeated)
            unresolved.append(hole)
            continue
        first = values[0]
        extrapolated = first[0] > 0
        if extrapolated:
            missing_zero.append(hole)
        origin = tuple(float(collar[0][k]) for k in ("x", "y", "z"))
        x, y, z = origin
        previous = (0, first[1], first[2], None)
        trajectory.append(dict(hole_id=hole, depth=0, x=x, y=y, z=z,
                               source_survey_row=first[3] if first[0] == 0 else None,
                               first_attitude_extended=extrapolated))
        for current in values:
            md, _, _, row_no = current
            if md > 0:
                dx, dy, dz = delta(md - previous[0], previous[1:3], current[1:3])
                x += dx
                y += dy
                z += dz
                trajectory.append(dict(hole_id=hole, depth=md, x=x, y=y, z=z, source_survey_row=row_no,
                                       first_attitude_extended=extrapolated))
            previous = current
        vertical = origin[2] - z
        md = values[-1][0]
        displacement.append(dict(hole_id=hole, measured_depth=md, vertical_depth=vertical,
                                 horizontal_displacement=math.hypot(x-origin[0], y-origin[1]),
                                 TVD_MD=vertical/md if md else None))
    ref("drill_survey", {"count": len(rows), "invalid": invalid, "duplicate_depths": duplicates,
                         "original_order_decreases": disorder, "missing_zero_station": missing_zero,
                         "no_valid_trajectory": unresolved})
    ref("drill_trajectory", {"rows": trajectory, "unresolved_holes": unresolved})
    ref("drill_md_tvd", displacement)


def assay_references(drill1, drill2):
    assays, invalid, overlap = intervals(drill1["assay"])
    litho, invalid_litho, overlap_litho = intervals(drill1["litho"])
    ref("drill_intervals", {
        "assay": {"valid_n": sum(map(len, assays.values())), "invalid": invalid, "overlaps": overlap},
        "litho": {"valid_n": sum(map(len, litho.values())), "invalid": invalid_litho, "overlaps": overlap_litho},
    })
    by_window = defaultdict(list)
    excluded = {i for pair in overlap for i in pair["rows"]}
    for hole, assay_rows in assays.items():
        for a, b, row in assay_rows:
            value = finite(row["au"])
            if value is None or row["row_number"] in excluded:
                continue
            for w in range(math.floor(a / 2), math.ceil(b / 2)):
                length = max(0, min(b, 2*w+2) - max(a, 2*w))
                if length:
                    by_window[hole, w].append((length, value, row["row_number"]))
    composite = []
    for (hole, w), rows in sorted(by_window.items()):
        length = sum(x[0] for x in rows)
        composite.append({"hole_id": hole, "from": w*2, "to": w*2+2, "sampled_length": length,
                          "coverage": length/2, "au_native": sum(a*b for a, b, _ in rows)/length,
                          "source_rows": [i for _, _, i in rows]})
    ref("drill_composites", {"rows": composite, "excluded_overlapping_rows": sorted(excluded),
                             "weighted_sum": sum(row["sampled_length"]*row["au_native"] for row in composite)})

    other, invalid, overlap = intervals(drill2["assay"])
    excluded = {i for pair in overlap for i in pair["rows"]}
    ref("drill_coverage", {"rows": coverage(other, drill2["collar"]), "invalid_intervals": invalid})
    rows = []
    for hole, values in other.items():
        accepted = [(b-a, finite(r["au"])) for a, b, r in values
                    if r["row_number"] not in excluded and finite(r["au"]) is not None]
        length = sum(s for s, _ in accepted)
        rows.append(dict(hole_id=hole, samples=len(accepted), length=length,
                         weighted_au=sum(s*v for s, v in accepted)/length if length else None,
                         arithmetic_au=stats.mean(v for _, v in accepted) if accepted else None))
    ref("drill_hole_summary", {"rows": rows, "invalid_intervals": invalid,
                               "excluded_overlapping_rows": sorted(excluded)})


def drill():
    one, two = drill_tables("drill1"), drill_tables("drill2")
    collars = defaultdict(list)
    for c in one["collar"]:
        collars[c["hole_id"]].append(c)
    ref("drill_collar", {"rows": len(one["collar"]), "unique_holes": len(collars),
                         "duplicates": {k: v for k, v in collars.items() if len(v) > 1},
                         "invalid_coordinates": [r for r in one["collar"]
                                                 if any(finite(r[k]) is None for k in ("x", "y", "z"))]})
    ref("drill_fk", {
        "orphan_rows": {kind: [r for r in rows if r["hole_id"] not in collars]
                        for kind, rows in one.items() if kind != "collar"},
        "per_hole": {hole: {kind: sum(r["hole_id"] == hole for r in rows) for kind, rows in one.items()}
                     for hole in collars},
    })
    survey_references(collars, one["survey"])
    assay_references(one, two)


def soil():
    import geopandas as gpd
    import numpy as np

    rows = []
    for medium in ("2mm", "80mesh"):
        points = gpd.read_file(MINING / f"soil/soil_{medium}_MGA51.shp", engine="pyogrio")
        for i, point in points.iterrows():
            rows.append(dict(medium=medium, row_number=int(i+1), SampleNo=point.SampleNo, Source=point.Source,
                             x=point.geometry.x, y=point.geometry.y, Au_ppb=finite(point.Au_ppb)))
    summary = {}
    for medium in ("2mm", "80mesh"):
        selected = [row for row in rows if row["medium"] == medium]
        values = [row["Au_ppb"] for row in selected if row["Au_ppb"] is not None]
        median = stats.median(values)
        mad = stats.median(abs(x-median) for x in values)
        q1, q3 = map(float, np.quantile(values, [0.25, 0.75], method="linear"))
        summary[medium] = dict(n=len(values), missing=len(selected)-len(values), min=min(values), max=max(values),
                               median=median, q1=q1, q3=q3, MAD=mad, threshold=median+3*1.4826*mad)
    ref("soil_stats", summary)
    ref("soil_units", [dict(row, Au_ppm=None if row["Au_ppb"] is None else row["Au_ppb"]/1000) for row in rows])
    ref("soil_log", [
        dict(row, log10=math.log10(row["Au_ppb"]) if row["Au_ppb"] and row["Au_ppb"] > 0 else None,
             status="missing" if row["Au_ppb"] is None else ("nonpositive" if row["Au_ppb"] <= 0 else "valid"))
        for row in rows
    ])
    ref("soil_anomalies", {"thresholds": summary,
                           "anomalies": [row for row in rows if row["Au_ppb"] is not None
                                         and row["Au_ppb"] > summary[row["medium"]]["threshold"]]})
    duplicate_groups = {}
    for fields in [("medium", "SampleNo"), ("medium", "x", "y"), ("SampleNo",)]:
        grouped = defaultdict(list)
        for row in rows:
            grouped[tuple(row[k] for k in fields)].append(row)
        duplicate_groups["+".join(fields)] = [
            members for members in grouped.values()
            if len(members) > 1 and (len(fields) > 1 or len({r["medium"] for r in members}) > 1)
        ]
    ref("soil_duplicates", duplicate_groups)
    batches = defaultdict(list)
    for row in rows:
        batches[row["medium"], row["Source"]].append(row["Au_ppb"])
    result = []
    for (medium, source), values in sorted(batches.items()):
        valid = [v for v in values if v is not None]
        result.append(dict(medium=medium, Source=source, n=len(values), missing=len(values)-len(valid),
                           median=stats.median(valid), min=min(valid), max=max(valid)))
    ref("soil_source", result)


def mesh():
    from math import dist

    models = {}
    for path in sorted((MINING / "meshes").glob("*.obj")):
        vertices, faces = [], []
        for line in path.read_text(encoding="ascii").splitlines():
            tokens = line.split()
            if tokens and tokens[0] == "v":
                vertices.append(tuple(map(float, tokens[1:])))
            if tokens and tokens[0] == "f":
                faces.append(tuple(map(int, tokens[1:])))
        edges = Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face, face[1:] + face[:1]))
        zero = 0
        for f in faces:
            a,b,c = (vertices[idx-1] for idx in f)
            u, v = [x-y for x,y in zip(b,a)], [x-y for x,y in zip(c,a)]
            cross = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
            if dist(cross, (0,0,0)) <= 1e-10:
                zero += 1
        idxs = [idx for face in faces for idx in face]
        bbox = [min(v[i] for v in vertices) for i in range(3)] + [max(v[i] for v in vertices) for i in range(3)]
        models[path.stem.rsplit("_", 1)[1]] = dict(
            file=path.name, vertices=len(vertices), faces=len(faces), non_triangles=0, bbox=bbox,
            index_range=[min(idxs), max(idxs)], boundary_edges=sum(n == 1 for n in edges.values()),
            nonmanifold_edges=sum(n > 2 for n in edges.values()),
            two_use_edges=sum(n == 2 for n in edges.values()), zero_area_faces=zero,
            duplicate_faces=len(faces)-len({tuple(sorted(f)) for f in faces}),
        )
    ref("mesh_inventory", models)
    ref("mesh_topology", models)


def blocks():
    rows = csv_rows(MINING / "blocks/synthetic_5m_blocks.csv")
    by_xyz, by_code, by_domain = defaultdict(list), defaultdict(set), defaultdict(list)
    probability = []
    for row in rows:
        by_xyz[tuple(row[k] for k in "XYZ")].append(row)
        by_code[row["Series_Code"]].add(row["Series"])
        value = finite(row["Probability"])
        if value is None or not 0 <= value <= 1:
            probability.append(row)
        else:
            by_domain[row["Series"]].append(value)
    conflicts, duplicates = [], []
    counts = Counter()
    for group in by_xyz.values():
        if len(group) > 1:
            duplicates.append([r["row_number"] for r in group])
        if len({r["Series"] for r in group}) > 1:
            conflicts.append([r["row_number"] for r in group])
        else:
            counts[group[0]["Series"]] += 1
    volume = {name: {"count": n, "volume_m3": 125*n} for name, n in sorted(counts.items())}
    density = read_json(BUNDLED / "resource/scenario_density.json")["density_t_m3"]
    ref("block_volume", {"rows": len(rows), "unique_xyz": len(by_xyz), "accepted_xyz": sum(counts.values()),
                          "duplicates": duplicates, "conflicts": conflicts, "by_domain": volume})
    ref("block_quality", {"invalid_probability": probability, "duplicate_xyz_rows": duplicates,
                           "conflicting_xyz": conflicts,
                           "series_code_conflicts": {k: sorted(v) for k, v in by_code.items() if len(v) > 1},
                           "valid_probability_by_domain": {k: dict(n=len(v), min=min(v), max=max(v), median=stats.median(v))
                                                           for k, v in by_domain.items()}})
    ref("block_mass", {"density_t_m3": density, "excluded_conflicting_groups": conflicts, "by_domain": {
        k: dict(v, tonnes=round(v["volume_m3"]*density, 8)) for k, v in volume.items()
    }})


def main():
    drill()
    soil()
    mesh()
    blocks()


if __name__ == "__main__":
    main()
