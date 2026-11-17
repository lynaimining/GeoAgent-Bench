"""Generate the invented mining inputs used by the public edition.

Coordinates, sample identifiers, assays and meshes come from the functions below.
The generator consumes no project file.
"""

import argparse
import shutil
from pathlib import Path

from .common import identity, write_csv, write_json


def drilling(base):
    table_names = ["01_collar.csv", "02_survey.csv", "03_assay.csv", "04_litho.csv"]
    for series, count in ((1, 10), (2, 5)):
        collars, surveys, assays, lithology = [], [], [], []
        for i in range(count):
            hole = f"DEMO-{series}-{i + 1:02d}"
            max_depth = 32 + 4 * (i % 4)
            collar = dict(hole_id=hole, x=510000 + 29 * i, y=6450000 + 13 * (i % 4), z=352 + i)
            collars.append(collar if series == 1 else dict(collar, max_depth=max_depth))
            stations = [0, 12, 24, 30]
            if i == 1:
                stations[0] = 3
            if series == 1 and i == count - 1:
                stations = []
            for j, md in enumerate(stations):
                surveys.append(dict(hole_id=hole, depth=md, dip=-75 + i + 2 * j, azimuth=(24 * i + 8 * j) % 360))
            intervals = [(a, min(a + 3, max_depth)) for a in range(0, max_depth, 3)]
            if series == 2 and i == 1:
                intervals = intervals[1:3] + intervals[4:] + [(max_depth, max_depth + 1.5)]
            if series == 2 and i == 3:
                intervals.append((8.0, 11.0))
            start, end = ("from_m", "to_m") if series == 1 else ("from", "to")
            for j, (a, b) in enumerate(intervals):
                value = round(0.07 + ((7 * i + 3 * j) % 19) / 10, 2)
                row = {"hole_id": hole, start: a, end: b, "au": value}
                if series == 2:
                    row["sample_id"] = f"ASSAY-{i + 1:02d}-{j + 1:02d}"
                assays.append(row)
            for a, b, rock in ((0, 7.5, "OX"), (7.5, 17.5, "BAS"), (17.5, max_depth, "BAS-alt")):
                lithology.append({"hole_id": hole, start: a, end: b, "lithology": rock})
        for name, rows in zip(table_names, [collars, surveys, assays, lithology]):
            write_csv(base / f"drill{series}" / name, rows)
        if series == 1:
            bad_collar = [*collars, dict(collars[1])]
            bad_survey = [*surveys, dict(surveys[0], dip=-95)]
            bad_assay = [*assays, dict(assays[1], hole_id="DEMO-ORPHAN")]
            bad_lithology = [*lithology, dict(lithology[1], from_m=6.0, to_m=12.0)]
            for name, rows in zip(table_names, [bad_collar, bad_survey, bad_assay, bad_lithology]):
                write_csv(base / "drill_fault" / name, rows)
    (base / "drill_fault/README.md").write_text(
        "合成钻孔数据的质量检查场景。CSV 行号从第一条数据记录计为 1。\n",
        encoding="utf-8", newline="\n",
    )
    write_csv(base / "drill_plan/drilling_plan_fixture.csv", [
        {"hole_id": f"PLAN-{i+1:02d}", "x": 510000 + 36 * i, "y": 6450000 + 13 * (i % 4),
         "z": 352 + 2 * i, "depth": 42, "dip": -67, "azimuth": 110}
        for i in range(7)
    ])


def soil(base):
    import geopandas as gpd
    from shapely.geometry import Polygon

    soil_dir = base / "soil"
    soil_dir.mkdir(parents=True, exist_ok=True)
    for name, count, shift in (("2mm", 266, 0), ("80mesh", 212, 1)):
        ids, grades, batches, xy = [], [], [], []
        for i in range(count):
            sample = max(0, i - 1) if i in (29, 61) else i
            position = i - 1 if i in (31, 61) else i
            au = round(3 + ((97 * i + 23 * shift) % 81) * 0.25 + (40 if i % 53 == 0 else 0), 2)
            if i in (4, 11, 18):
                au = {4: 0.0, 11: -1.0, 18: None}[i]
            ids.append(f"SYN-{sample:03d}")
            grades.append(au)
            batches.append(f"Batch-{i % 3 + 1}")
            xy.append((509900 + (position % 19) * 15 + 4 * shift, 6449900 + (position // 19) * 15 + 3 * shift))
        layer = gpd.GeoDataFrame(
            {"SampleNo": ids, "Au_ppb": grades, "Source": batches},
            geometry=gpd.points_from_xy([x for x, _ in xy], [y for _, y in xy]),
            crs="EPSG:28351",
        )
        layer.to_file(soil_dir / f"soil_{name}_MGA51.shp", engine="pyogrio", encoding="UTF-8")
    backup = base / "soil_backup"
    backup.mkdir(parents=True, exist_ok=True)
    for file in soil_dir.iterdir():
        shutil.copyfile(file, backup / file.name)
    boundary = base / "tenement"
    boundary.mkdir(parents=True, exist_ok=True)
    polygon = Polygon([(509945, 6449930), (510140, 6449930), (510140, 6450080), (509945, 6450080)])
    gpd.GeoDataFrame({"permit_id": ["SYNTH-TRAINING"]}, geometry=[polygon], crs="EPSG:28351").to_file(
        boundary / "Synthetic_Polygon_MGA51.shp", engine="pyogrio", encoding="UTF-8"
    )


def write_box(path, bounds, variant):
    x0, y0, z0, x1, y1, z1 = bounds
    vertices = [(x0,y0,z0), (x1,y0,z0), (x1,y1,z0), (x0,y1,z0),
                (x0,y0,z1), (x1,y0,z1), (x1,y1,z1), (x0,y1,z1)]
    faces = [(1,3,2), (1,4,3), (5,6,7), (5,7,8), (1,2,6), (1,6,5),
             (2,3,7), (2,7,6), (3,4,8), (3,8,7), (4,1,5), (4,5,8)]
    if variant == "P30":
        vertices.append((x0, y0, (z0 + z1) / 2))
        faces = faces[:-1] + [faces[0], (1,5,9)]
    if variant == "P70":
        faces[6] = tuple(reversed(faces[6]))
    lines = ["# Synthetic geometry for evaluation"] + ["v %s %s %s" % p for p in vertices]
    lines.extend("f %s %s %s" % f for f in faces)
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def models(base, path_prefix):
    meshes = base / "meshes"
    meshes.mkdir(parents=True, exist_ok=True)
    for i, label in enumerate(("P30", "P50", "P70")):
        bounds = (510008 + 8*i, 6450002 + 6*i, 275 + 7*i,
                  510115 - 8*i, 6450080 - 7*i, 338 - 7*i)
        write_box(meshes / f"synthetic_solid_{label}.obj", bounds, label)
    velocity = base / "velocity/velocity_15m_EPSG32751.csv"
    write_csv(velocity, [
        dict(X=510015 + 15*i, Y=6450015 + 15*j, Z=270 + 15*k, Vs=2.7 + (2*i+j+k)/100)
        for k in range(5) for j in range(5) for i in range(7)
    ])
    classes = ["Basement", "Surficial", "Volcanic", "Regolith", "Intrusive"]
    blocks = []
    for k in range(5):
        for j in range(7):
            for i in range(11):
                code = (i + 2*j + 3*k) % len(classes)
                blocks.append(dict(X=510020 + 5*i, Y=6450015 + 5*j, Z=275 + 5*k,
                                   Series_Code=code, Probability=round(0.34 + (i+j+k) / 40, 3),
                                   Series=classes[code]))
    blocks[21]["Probability"] = 1.1
    blocks[59]["Probability"] = ""
    blocks.append(dict(blocks[4]))
    blocks.append(dict(blocks[7], Series="ConflictingLabel"))
    write_csv(base / "blocks/synthetic_5m_blocks.csv", blocks)
    files = [base / "drill1/01_collar.csv", meshes / "synthetic_solid_P50.obj", velocity]
    write_json(base / "scene/source-manifest.json", {
        "fixture": "Synthetic training project",
        "scene": {"horizontal_crs": "EPSG:28351", "coordinate_unit": "m", "vertical_datum": "unknown"},
        "sources": [
            {
                "path": path_prefix + "/" + path.relative_to(base).as_posix(),
                "role": role,
                "crs_evidence": "file name only" if path == velocity else "synthetic scene convention",
                "data_status": "synthetic", **identity(path),
            }
            for path, role in zip(files, ["collar", "interpretation_mesh", "velocity_hint"])
        ],
        "scope": "Inventory metadata may refer to fixtures outside a single task's input selection.",
    })
    write_json(base / "scene/scene.json", {
        "kind": "portable_scene_description", "crs": "EPSG:28351",
        "layers": ["collar", "interpretation_mesh"], "camera": "choose in the installed application",
    })


def generate(base):
    drilling(base)
    soil(base)
    models(base, "data/synthetic/mining")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    generate(args.destination)


if __name__ == "__main__":
    main()
