# Data sources, versions and terms

The MIT license applies to benchmark-authored software and documentation. Benchmark-authored teaching prompts and generated synthetic datasets are available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution: GeoAgent-Bench contributors, public edition 1.0. The third-party files and prompts listed below retain their own terms.

| Source | Pinned artifact | Terms and retrieval |
|---|---|---|
| GABench / GeoAgentBench | [Commit 357d0f5](https://github.com/GeoX-Lab/GABench/tree/357d0f531d55bfbd701a79a77af86c1db3b22325) | Repository Apache-2.0. Original files and separate data provenance stay with the author distribution. Selected Git LFS files are fetched from the pinned commit and verified by SHA-256. |
| GeoBenchX | [Commit 0edf610](https://github.com/Solirinai/GeoBenchX/tree/0edf6109ea5dca3e70fdfe081d39c9ccd0f832fb) | MIT repository. Download the [author's Data.zip](https://drive.google.com/file/d/10hLDCTMnaMAXyUCxFjUt4iK7tX9XyXZu/view), read `Data/Data_Sources.bib`, and observe the component data terms. The archive hash is in the manifest. |
| GeoAgentEval | [Commit 3da32ce](https://github.com/hsd2514/geoagenteval/tree/3da32ce6eb13dac8e0ac263e1e9830da67b8a56b) | MIT. The author created the synthetic cities, SQL seeds, original task texts and end-state verifiers. Selected components are reproduced with the original [license](licenses/GeoAgentEval.txt). |
| Earth-Bench-V2 | [Dataset revision 5115836](https://huggingface.co/datasets/LvZTTTT/Earth-Bench-V2/tree/5115836f47f19c15c79c8ee3ca6f10869bd6eaf2) | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Image/raster files, original English questions and choices are fetched from the author. Use `--accept-noncommercial` for this track after reviewing its terms. |
| GeoNatureAgent | [Commit 88daf4d](https://github.com/gabrielireland/GeoNatureAgent_Benchmark/tree/88daf4d299f68688d5153f1d6a1e9530ffba17bd), [Zenodo record 20454498](https://zenodo.org/records/20454498) | Repository Apache-2.0, author data release CC BY 4.0. Cite the original sources listed in the data release, including the original Copernicus and administrative boundary datasets where applicable. |
| OpenEarthAgent | [Dataset revision e7174dd](https://huggingface.co/datasets/MBZUAI/OpenEarthAgent/tree/e7174ddb960777ed8395393bc435c74596a6a20c) | Dataset package Apache-2.0. Preserve source-layer attribution, including [© OpenStreetMap contributors](https://www.openstreetmap.org/copyright) and ODbL terms when applicable. The input builder extracts selected layers from the author's archive and removes result columns. |
| GeoAgent-Bench synthetic fixtures | [Generator](geoagent_bench/fixtures.py), [bundled inputs](assets/bundled/data/synthetic/) | Invented data for drilling, soil chemistry, mesh inspection, velocity, blocks and laboratory tasks. Synthetic replacements are identified in the catalog. |

[Source registry](tasks/sources.json) · [Asset manifest](assets/manifest.json) · [License texts](licenses/)

- The date, citation key and source locator on each task provide credit and distinguish the original item from adaptations.
- For downloaded archives the controller verifies the original file and reads only named members. It stores derived input identities in cache receipts. The GeoPackage export can differ in file bytes by GDAL version, while preserving the fixed source member and layer selection.
- The public catalog includes task objectives and scoring contracts. For the six Earth-Bench-V2 original tasks, the pinned dataset supplies the full original wording and choices on preparation. The evaluation dialogs and ground truth are withheld from the staged Agent.
- Compound source terms apply to adapted questions and derived data. For commercial use, review the rights on each selected input through the original provider.
