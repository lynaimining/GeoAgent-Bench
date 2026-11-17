"""Fetch and stage pinned data from the original distributors."""

import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

from .common import ROOT, identity, matches, path_at, read_json, sha256, write_json

MANIFEST = ROOT / "assets/manifest.json"


def checked_copy(stream, destination, record):
    """Check length and hash while streaming, then atomically commit the file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        name = Path(temporary.name)
        try:
            digest = hashlib.sha256()
            count = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                count += len(chunk)
                if count > record["bytes"]:
                    raise ValueError(f"Downloaded more than manifest allows: {destination.name}")
                digest.update(chunk)
                temporary.write(chunk)
            if count != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise ValueError(f"Source bytes or SHA-256 differ from manifest: {destination.name}")
            temporary.close()
            name.replace(destination)
        finally:
            temporary.close()
            name.unlink(missing_ok=True)


class Inputs:
    def __init__(self, cache, *, library=None, archive=None, offline=False, accept_nc=False):
        self.cache = Path(cache).resolve()
        self.library = Path(library).resolve() if library else None
        self.archive = Path(archive).resolve() if archive else None
        self.offline = offline
        self.accept_nc = accept_nc
        self.manifest = read_json(MANIFEST)
        self.verified = {}

    def require_terms(self, task):
        if task["noncommercial_data"] and not self.accept_nc:
            raise ValueError("This case uses Earth-Bench-V2 (CC BY-NC 4.0). See DATA_LICENSES.md and use --accept-noncommercial.")

    def _cached(self, entry, dest):
        return matches(dest, entry)

    def _fetch(self, url, dest, entry):
        if self.offline:
            raise ValueError(f"Offline cache miss for {dest.name}. Import the author snapshot with --library.")
        if urlparse(url).scheme != "https":
            raise ValueError("Only HTTPS source URLs are supported")
        with urlopen(Request(url, headers={"User-Agent": "GeoAgent-Bench/1.0"}), timeout=60) as response:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Source redirected outside HTTPS")
            checked_copy(response, dest, entry)

    def _use_local(self, entry, dest, source):
        if source is None or not source.is_file():
            return False
        if entry.get("library_checkout_crlf"):
            canonical = source.read_bytes().replace(b"\r\n", b"\n")
            checked_copy(io.BytesIO(canonical), dest, entry)
        else:
            with source.open("rb") as stream:
                checked_copy(stream, dest, entry)
        return True

    def _library_path(self, entry):
        return path_at(self.library, entry["library_path"]) if self.library and entry.get("library_path") else None

    def _payload(self, key):
        if ("payload", key) in self.verified:
            return self.verified["payload", key]
        entry = self.manifest["payloads"][key]
        dest = path_at(self.cache / "payloads", key)
        if entry.get("noncommercial") and not self.accept_nc:
            raise ValueError("Supply --accept-noncommercial for Earth-Bench-V2.")
        local_file = self.archive if key == "geobenchx.zip" and self.archive else self._library_path(entry)
        if not self._cached(entry, dest) and not self._use_local(entry, dest, local_file):
            if "drive_id" in entry:
                if self.offline:
                    raise ValueError("Supply the author's Data.zip with --geobenchx-archive.")
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
                    downloaded = Path(tmp) / "Data.zip"
                    command = [sys.executable, "-m", "gdown", entry["drive_id"], "-O", str(downloaded)]
                    try:
                        subprocess.run(command, check=True, timeout=1800)
                        self._use_local(entry, dest, downloaded)
                    except (subprocess.SubprocessError, OSError, ValueError) as error:
                        raise ValueError(
                            "GeoBenchX archive download failed. Download Data.zip from the link in "
                            "DATA_LICENSES.md and pass --geobenchx-archive."
                        ) from error
            else:
                self._fetch(entry["url"], dest, entry)
        self.verified["payload", key] = dest
        return dest

    def get(self, relative):
        if ("file", relative) in self.verified:
            return self.verified["file", relative]
        entry = self.manifest["files"][relative]
        if entry.get("noncommercial") and not self.accept_nc:
            raise ValueError("Supply --accept-noncommercial for Earth-Bench-V2.")
        mode = entry["mode"]
        dest = path_at(self.cache / "inputs", relative)
        if mode == "bundled":
            dest = path_at(ROOT / "assets/bundled", relative)
            if not self._cached(entry, dest):
                raise ValueError(f"Bundled fixture changed: {relative}")
        elif mode == "derived":
            self._build(entry["assembly"], relative, dest)
        elif not self._cached(entry, dest) and not self._use_local(entry, dest, self._library_path(entry)):
            if mode == "zip":
                with ZipFile(self._payload(entry["archive"])) as archive:
                    with archive.open(entry["member"]) as stream:
                        checked_copy(stream, dest, entry)
            elif mode == "url":
                self._fetch(entry["url"], dest, entry)
            else:
                raise ValueError(f"Unknown input retrieval mode: {mode}")
        self.verified["file", relative] = dest
        return dest

    def _build(self, key, relative, dest):
        from . import preprocess

        assembly = self.manifest["assemblies"][key]
        recorded = path_at(self.cache / "receipts", relative + ".json")
        recipe = sha256(Path(preprocess.__file__))
        if dest.is_file() and recorded.is_file():
            receipt = read_json(recorded)
            if receipt.get("assembly") == assembly and receipt.get("code_sha256") == recipe:
                if matches(dest, receipt["output"]):
                    return
        inputs = {
            name: self._payload(item["payload"]) if "payload" in item else self.get(item["asset"])
            for name, item in assembly["inputs"].items()
        }
        self.cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.cache) as tmp:
            produced = preprocess.build(assembly, inputs, Path(tmp))
            for output_relative in assembly["outputs"]:
                output = produced[Path(output_relative).name]
                target = path_at(self.cache / "inputs", output_relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                output.replace(target)
                write_json(path_at(self.cache / "receipts", output_relative + ".json"), {
                    "assembly": assembly,
                    "code_sha256": recipe,
                    "inputs": {name: identity(path) for name, path in inputs.items()},
                    "output": identity(target),
                })

    def source_prompt(self, task):
        prompt = task.get("original_prompt", "")
        key = task.get("earth_original")
        if key:
            record = read_json(self._payload("earth-questions.json"))[key]
            prompt = record["evaluation"][0]["question"]
            choices = record.get("choices")
            if isinstance(choices, dict):
                rendered = "\n".join(f"{key}. {value}" for key, value in choices.items())
            else:
                rendered = "\n".join(f"{chr(65+i)}. {value}" for i, value in enumerate(choices or []))
            prompt += "\n\n" + rendered if rendered else ""
        return prompt

    def fetch_task(self, task):
        self.require_terms(task)
        inputs = {rel: self.get(rel) for rel in task["input_paths"]}
        return inputs, self.source_prompt(task)

    def stage_files(self, inputs, destination):
        for relative, source in inputs.items():
            target = path_at(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
