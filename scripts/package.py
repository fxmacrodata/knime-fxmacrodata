"""Build from an explicit public file allowlist, with no repository-wide copy."""
from __future__ import annotations

import argparse
from copy import copy
import hashlib
from hashlib import sha256
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    "knime.yml", "pixi.toml", "pixi.lock", "LICENSE.TXT", "README.md", "CHANGELOG.md", "OPERATIONS.md",
    "src/__init__.py", "src/extension.py", "src/tables.py", "src/response_safety.py", "icons/fxmacrodata.png", "icons/fxmacrodata-category.png",
)
SOURCE_FILES = RUNTIME_FILES + (
    "scripts/package.py", "scripts/operation_matrix.py", "tests/conftest.py", "tests/test_nodes.py",
    "tests/test_package.py", "pytest.ini", "ruff.toml",
)


def _bundler_environment():
    # KNIME's build summary prints Unicode status glyphs, including on Windows.
    return dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def _portable_license_metadata(data: bytes, wheel_names: list[str]) -> bytes:
    """Repair a native license-report heading without changing license text."""
    text = data.decode("utf-8")
    absolute = re.compile(r'^(?:[A-Za-z]:[\\/]|/|file://)', re.IGNORECASE)
    def is_absolute(line):
        decoded = line.lstrip().lstrip('"')
        for _ in range(4):
            value = unquote(decoded)
            if value == decoded:
                break
            decoded = value
        return bool(absolute.match(decoded))
    lines = text.splitlines(keepends=True)
    if sum(is_absolute(line) for line in lines) > 1:
        raise ValueError("Unexpected generated license source headings.")
    for index, line in enumerate(lines):
        if not is_absolute(line):
            continue
        # The native reporter parses a local wheel path as a package name.
        # This package has one wheel; retain the original license classification.
        if len(wheel_names) != 1 or not line.rstrip("\r\n").endswith(": UNKNOWN"):
            raise ValueError("Unexpected absolute path in generated license metadata.")
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        lines[index] = wheel_names[0] + ": UNKNOWN" + ending
    return "".join(lines).encode("utf-8")


def _replace_zip_members(path: Path, replacements: dict[str, bytes]):
    temporary = path.with_name(path.name + ".portable-tmp")
    if temporary.exists():
        raise ValueError("Choose a fresh build output directory.")
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, "w") as output:
        output.comment = source.comment
        for entry in source.infolist():
            if entry.filename in replacements:
                output.writestr(copy(entry), replacements[entry.filename])
            else:
                with source.open(entry) as incoming, output.open(copy(entry), "w") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=1024 * 1024)
    os.replace(temporary, path)


def _artifact_path(site: Path, artifact) -> Path:
    directory = {"osgi.bundle": "plugins", "org.eclipse.update.feature": "features"}.get(artifact.get("classifier"))
    if directory is None:
        raise ValueError("Unexpected p2 artifact classifier.")
    name = artifact.get("id", "") + "_" + artifact.get("version", "") + ".jar"
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("Unsafe p2 artifact name.")
    path = (site / directory / name).resolve()
    if not path.is_relative_to(site.resolve()) or not path.is_file():
        raise ValueError("Missing p2 artifact.")
    return path


def _artifact_values(path: Path):
    digests = {name: hashlib.new(algorithm) for name, algorithm in (("sha-1", "sha1"), ("sha-256", "sha256"), ("sha-512", "sha512"))}
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            for digest in digests.values():
                digest.update(chunk)
    return {"artifact.size": str(path.stat().st_size), "download.size": str(path.stat().st_size), **{"download.checksum." + name: digest.hexdigest() for name, digest in digests.items()}}


def portable_update_site(site: Path):
    """Normalize native generated metadata and refresh both p2 checksum indexes.

    Signed JARs are rejected. Dependency payloads and licenses are never edited.
    Content metadata identifies versions and remains byte-for-byte unchanged.
    """
    site = site.resolve()
    with zipfile.ZipFile(site / "artifacts.jar") as archive:
        original_xml = archive.read("artifacts.xml")
    if lzma.decompress((site / "artifacts.xml.xz").read_bytes()) != original_xml:
        raise ValueError("The two p2 artifact indexes disagree.")
    tree = ET.fromstring(original_xml)
    supported = {"artifact.size", "download.size", "download.checksum.sha-1",
                 "download.checksum.sha-256", "download.checksum.sha-512"}
    artifacts = []
    for artifact in tree.findall("./artifacts/artifact"):
        path = _artifact_path(site, artifact)
        properties = artifact.findall("./properties/property")
        names = {prop.get("name", "") for prop in properties}
        if not supported.issubset(names) or any(
            name.startswith("download.checksum.") and name not in supported
            for name in names
        ):
            raise ValueError("Unsupported p2 checksum metadata.")
        artifacts.append((path, properties))

    # Complete validation before changing any JAR or checksum index.
    metadata = "conda_licenses/metadata_licenses.txt"
    replacements = []
    for jar in sorted((site / "plugins").glob("*.channel.bin.*_*.jar")):
        with zipfile.ZipFile(jar) as archive:
            names = archive.namelist()
            manifest = archive.read("META-INF/MANIFEST.MF") if "META-INF/MANIFEST.MF" in names else b""
            signatures = any(
                name.upper().startswith("META-INF/") and (
                    name.upper().endswith((".SF", ".RSA", ".DSA", ".EC"))
                    or name.upper().startswith("META-INF/SIG-")
                ) for name in names
            )
            if signatures or re.search(rb"(?im)^[^\r\n:]*(?:digest|signature)[^\r\n:]*:", manifest):
                raise ValueError("Cannot rewrite a signed native bundle.")
            if metadata not in names:
                continue
            wheels = [Path(name).name for name in names if name.startswith("env/pypi/") and name.endswith(".whl")]
            original = archive.read(metadata)
            portable = _portable_license_metadata(original, wheels)
        if original != portable:
            replacements.append((jar, portable))

    for jar, portable in replacements:
        _replace_zip_members(jar, {metadata: portable})
    changes = [jar.name for jar, _ in replacements]
    for path, properties in artifacts:
        values = _artifact_values(path)
        for prop in properties:
            if prop.get("name") in values:
                prop.set("value", values[prop.get("name")])
    xml = b"<?xml version='1.0' encoding='UTF-8'?>\n<?artifactRepository version='1.1.0'?>\n" + ET.tostring(tree, encoding="utf-8")
    _replace_zip_members(site / "artifacts.jar", {"artifacts.xml": xml})
    (site / "artifacts.xml.xz").write_bytes(lzma.compress(xml))
    return changes


def build(destination: Path, bundle: bool = False):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    source = destination / "extension-source"
    if source.exists():
        raise ValueError("Choose a new output directory; the staged source already exists.")
    source.mkdir()
    manifest = []
    for relative in SOURCE_FILES:
        source_path = ROOT / relative
        path = source_path.resolve()
        if not path.is_relative_to(ROOT) or source_path.is_symlink() or not path.is_file():
            raise ValueError("Missing or unsafe allowlisted package file: " + relative)
        data = path.read_bytes()
        manifest.append({"path": relative, "sha256": sha256(data).hexdigest(), "size": len(data)})
        if relative in RUNTIME_FILES:
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    archive = destination / "knime-fxmacrodata-0.1.0-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for item in manifest:
            info = zipfile.ZipInfo(item["path"], date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            output.writestr(info, (ROOT / item["path"]).read_bytes())
    (destination / "source-manifest.json").write_text(json.dumps({
        "package": "com.fxmacrodata.knime.fxmacrodata", "version": "0.1.0", "files": manifest,
        "source_archive_sha256": sha256(archive.read_bytes()).hexdigest(),
        "runtime_files": list(RUNTIME_FILES),
    }, indent=2) + "\n", encoding="utf-8")
    if bundle:
        executable = shutil.which("build-python-extension")
        if not executable:
            raise RuntimeError("Run this command in the Pixi build environment to use KNIME's bundler.")
        subprocess.run([
            executable, str(source), str(destination / "update-site"),
            "--update-sites-version", "5.12", "--generate-sbom",
        ], check=True, env=_bundler_environment())
        portable_update_site(destination / "update-site")
    print(json.dumps({"source_archive": str(archive), "source_files": len(manifest), "native_bundle_requested": bundle}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--bundle", action="store_true", help="Also build a KNIME update site using the native bundler.")
    args = parser.parse_args()
    build(args.destination, args.bundle)
