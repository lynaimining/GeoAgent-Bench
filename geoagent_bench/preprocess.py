"""Recreate the four types of derived inputs from verified upstream bytes."""

import json
import math
import struct
from collections import defaultdict
from contextlib import ExitStack
from zipfile import ZipFile

from .common import sha256, write_csv


def openearth(spec, inputs, output):
    import geopandas as gpd

    source = output / "unfiltered.gpkg"
    with ZipFile(inputs["archive"]) as archive:
        source.write_bytes(archive.read(spec["member"]))
    if sha256(source) != spec["member_sha256"]:
        raise ValueError("OpenEarthAgent GeoPackage member mismatch")
    target = output / "raw_inputs.gpkg"
    for layer_name in spec["layers"]:
        layer = gpd.read_file(source, layer=layer_name, engine="pyogrio")
        if layer_name == "area_boundary":
            allowed = {"name", "created_at", "year", "geometry"}
            layer = layer[[name for name in layer.columns if name in allowed]]
        else:
            derived_tokens = ("distance", "nearest", "rank", "score")
            layer = layer.drop(columns=[
                name for name in layer.columns if any(token in name.lower() for token in derived_tokens)
            ])
        layer.insert(0, "source_row", range(1, len(layer) + 1))
        layer.to_file(target, layer=layer_name, driver="GPKG", engine="pyogrio")
    return [target]


def elk(inputs, output):
    source = json.loads(inputs["observations"].read_text(encoding="utf-8-sig"))
    features = source["features"]
    stride = math.ceil(len(features) / 3000)
    selected = []
    for i in range(0, len(features), stride):
        feature = features[i]
        feature.setdefault("properties", {})["benchmark_source_row"] = i + 1
        selected.append(feature)
    source["features"] = selected
    target = output / "elk_sample.geojson"
    target.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8", newline="\n")
    return [target]


def building_triangles(inputs, output):
    """Decode type-31 Shapefile geometry where every part is a TriangleFan."""
    source = inputs["multipatch"].read_bytes()
    rows = []
    offset = 100
    while offset < len(source):
        record, words = struct.unpack_from(">ii", source, offset)
        offset += 8
        data = source[offset:offset + 2 * words]
        offset += 2 * words
        kind, = struct.unpack_from("<i", data)
        if kind == 0:
            continue
        if kind != 31:
            raise ValueError("Expected MultiPatch shape")
        n_parts, n_points = struct.unpack_from("<ii", data, 36)
        parts = list(struct.unpack_from(f"<{n_parts}i", data, 44)) + [n_points]
        types = struct.unpack_from(f"<{n_parts}i", data, 44 + 4*n_parts)
        start = 44 + 8*n_parts
        xy = [struct.unpack_from("<dd", data, start + 16*i) for i in range(n_points)]
        zs = struct.unpack_from(f"<{n_points}d", data, start + 16*n_points + 16)
        for part, flag in enumerate(types):
            if flag != 1:
                raise ValueError("Expected TriangleFan part")
            for tri, k in enumerate(range(parts[part]+1, parts[part+1]-1)):
                row = dict(source_record=record, source_part=part, triangle_in_part=tri)
                for vertex, idx in enumerate((parts[part], k, k+1), 1):
                    row.update({f"x{vertex}": xy[idx][0], f"y{vertex}": xy[idx][1], f"z{vertex}": zs[idx]})
                rows.append(row)
    target = output / "building_triangles.csv"
    write_csv(target, rows)
    return [target]


def feature_cells(inputs, features):
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.warp import transform_bounds

    with ExitStack() as stack:
        rasters = [stack.enter_context(rasterio.open(inputs[name])) for name in features]
        bounds = [transform_bounds(ds.crs, "EPSG:28355", *ds.bounds, densify_pts=21) for ds in rasters]
        xmin = max(b[0] for b in bounds)
        ymin = max(b[1] for b in bounds)
        xmax = min(b[2] for b in bounds)
        ymax = min(b[3] for b in bounds)
        cells = []
        for iy in range(math.floor(ymin / 5000), math.ceil(ymax / 5000)):
            for ix in range(math.floor(xmin / 5000), math.ceil(xmax / 5000)):
                x, y = (ix + 0.5)*5000, (iy + 0.5)*5000
                if xmin <= x < xmax and ymin <= y < ymax:
                    cells.append((f"{ix}:{iy}", x, y))
        columns = []
        for ds in rasters:
            tr = Transformer.from_crs("EPSG:28355", ds.crs, always_xy=True)
            coordinates = [tr.transform(x, y) for _, x, y in cells]
            values = [float(v[0]) if not np.ma.is_masked(v[0]) else np.nan
                      for v in ds.sample(coordinates, indexes=1, masked=True)]
            columns.append(values)
    matrix = np.column_stack(columns)
    keep = np.isfinite(matrix).all(axis=1)
    return [cell for cell, ok in zip(cells, keep) if ok], matrix[keep]


def centroids_oof(matrix, positive, folds):
    """Fit training-fold scaling and centroids independently for each outer fold."""
    import numpy as np

    scores = np.full(len(matrix), np.nan)
    for fold in sorted(set(folds)):
        train = folds != fold
        mean, std = matrix[train].mean(axis=0), matrix[train].std(axis=0)
        std[std == 0] = 1
        scaled = (matrix - mean) / std
        m_pos = scaled[train & positive].mean(axis=0)
        m_unl = scaled[train & ~positive].mean(axis=0)
        intercept = -0.5 * (m_pos @ m_pos - m_unl @ m_unl)
        scores[~train] = scaled[~train] @ (m_pos - m_unl) + intercept
    if not np.isfinite(scores).all():
        raise ValueError("An outer training fold did not support the P/U baseline")
    return scores


def mpm(spec, inputs, output):
    import geopandas as gpd
    import numpy as np

    features = spec["features"]
    cells, matrix = feature_cells(inputs, features)
    by_cell = defaultdict(set)
    occurrences = []
    points = gpd.read_file(inputs["occurrences"], engine="pyogrio").to_crs(28355)
    for i, point in points.iterrows():
        x, y = point.geometry.x, point.geometry.y
        value = point["DEPOSIT_ID"]
        ident = str(int(value)) if np.isfinite(value) else f"fid_{i+1}"
        cell = f"{math.floor(x/5000)}:{math.floor(y/5000)}"
        occurrences.append(dict(source_row=i+1, deposit_id=ident, x=x, y=y, cell_id=cell))
        by_cell[cell].add(ident)
    blocks = [(math.floor(x / 40000), math.floor(y / 40000)) for _, x, y in cells]
    block_fold = {block: i % 5 for i, block in enumerate(sorted(set(blocks)))}
    folds = np.array([block_fold[b] for b in blocks])
    positive = np.array([bool(by_cell[c]) for c, _, _ in cells])
    scores = centroids_oof(matrix, positive, folds)
    feature_rows, label_rows, fold_rows, oof_rows = [], [], [], []
    deposit_folds = defaultdict(set)
    for i, (cid, x, y) in enumerate(cells):
        fold = int(folds[i])
        for deposit in by_cell[cid]:
            deposit_folds[deposit].add(fold)
        coords = dict(cell_id=cid, x=x, y=y, area_km2=25.0)
        labels = dict(label="P" if positive[i] else "U", deposit_ids=";".join(sorted(by_cell[cid])))
        raw = dict(coords, **dict(zip(features, map(float, matrix[i]))))
        feature_rows.append(raw)
        label_rows.append(dict(raw, **labels))
        fold_rows.append(dict(raw, **labels, bx=blocks[i][0], by=blocks[i][1], fold=fold))
        oof_rows.append(dict(coords, **labels, fold=fold, score=float(scores[i]), held_out=1))
    if any(len(folds) > 1 for folds in deposit_folds.values()):
        raise ValueError("The same deposit crosses outer folds")
    names = ("feature_grid", "occurrences", "labeled_grid", "fold_grid", "oof_predictions")
    datasets = (feature_rows, occurrences, label_rows, fold_rows, oof_rows)
    targets = [output / f"{name}.csv" for name in names]
    for path, rows in zip(targets, datasets):
        write_csv(path, rows)
    return targets


def build(assembly, inputs, output):
    kind = assembly["kind"]
    if kind == "openearth":
        paths = openearth(assembly, inputs, output)
    elif kind == "elk":
        paths = elk(inputs, output)
    elif kind == "building_triangles":
        paths = building_triangles(inputs, output)
    elif kind == "mpm":
        paths = mpm(assembly, inputs, output)
    else:
        raise ValueError(f"Unknown assembly: {kind}")
    return {path.name: path for path in paths}
