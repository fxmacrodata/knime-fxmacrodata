"""Public artifacts contain only the explicit standalone integration files."""
from hashlib import sha256
import importlib.util
import json
import hashlib
import lzma
from pathlib import Path
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fxmd_package", ROOT / "scripts" / "package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def test_source_archive_and_runtime_staging_match_allowlists(tmp_path):
    package.build(tmp_path)
    manifest = json.loads((tmp_path / "source-manifest.json").read_text())
    assert {item["path"] for item in manifest["files"]} == set(package.SOURCE_FILES)
    staged = {path.relative_to(tmp_path / "extension-source").as_posix() for path in (tmp_path / "extension-source").rglob("*") if path.is_file()}
    assert staged == set(package.RUNTIME_FILES)
    archive = tmp_path / "knime-fxmacrodata-0.1.0-source.zip"
    assert sha256(archive.read_bytes()).hexdigest() == manifest["source_archive_sha256"]
    with zipfile.ZipFile(archive) as source:
        assert set(source.namelist()) == set(package.SOURCE_FILES)
        for entry in manifest["files"]:
            assert sha256(source.read(entry["path"])).hexdigest() == entry["sha256"]
    assert not any(part in staged for part in [".env", ".pixi", "api", "dev", "internal_dashboard"])


def test_metadata_and_every_node_documentation_include_backlinks():
    import yaml
    from src.extension import NODE_FACTORIES
    metadata = yaml.safe_load((ROOT / "knime.yml").read_text())
    assert metadata["group_id"] + "." + metadata["name"] == "com.fxmacrodata.knime.fxmacrodata"
    assert metadata["extension_module"] == "./src/extension"
    assert "https://fxmacrodata.com" in metadata["long_description"]
    for factory in NODE_FACTORIES.values():
        assert "https://fxmacrodata.com" in factory().__doc__


def test_dependency_lock_has_public_client_exact_wheel_hash():
    lock = (ROOT / "pixi.lock").read_text()
    assert "5c60ff217243ff4001f178d4fdd8c3c8ce29001ad1ea0a170ed96606f0dd07c8" in lock
    assert "file:///" not in lock and "Users/" not in lock


def test_module_import_matches_native_java_gateway_from_unrelated_directory(tmp_path):
    # PythonNodeGatewayFactory adds only the extension module's parent directory.
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONNOUSERSITE="1")
    code = "import extension; assert len(extension.NODE_FACTORIES) == 72; assert extension.ICON == 'icons/fxmacrodata.png'"
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr


def test_node_icon_paths_resolve_inside_native_extension_root():
    import knime.extension.nodes as nodes
    from src import extension
    # PythonExtensionParser resolves icon_path relative to knime.yml, not src/.
    for name in [*extension.NODE_FACTORIES, "operation_catalogue"]:
        path = (ROOT / nodes._nodes[name].icon_path).resolve()
        assert path.is_relative_to(ROOT) and path.is_file()


def test_native_build_summary_supports_unicode_under_legacy_console(monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    result = subprocess.run([sys.executable, "-c", "print(chr(0x2705))"], env=package._bundler_environment(), capture_output=True, timeout=60)
    assert result.returncode == 0
    assert result.stdout.decode("utf-8").strip() == "\u2705"


def native_site_fixture(root, signed=False):
    plugins = root / "plugins"
    plugins.mkdir()
    jar = plugins / "com.fxmacrodata.knime.fxmacrodata.channel.bin.linux.x86_64_0.1.0.test.jar"
    members = {
        "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
        "conda_licenses/metadata_licenses.txt": b"Other package: BSD\nC:\\build\\temporary\\integration: UNKNOWN\n",
        "conda_licenses/preserved.txt": b"Exact original third-party license text.\n",
        "env/pypi/fxmacrodata_public_client-0.1.0-py3-none-any.whl": b"synthetic locked wheel bytes",
        "env/channel/linux-64/fixture.conda": b"synthetic locked conda bytes",
    }
    if signed:
        members["META-INF/SIG-FIXTURE"] = b"synthetic signature marker"
    with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    tree = ET.Element("repository")
    artifacts = ET.SubElement(tree, "artifacts", size="1")
    artifact = ET.SubElement(artifacts, "artifact", classifier="osgi.bundle", id=jar.name.rsplit("_", 1)[0], version="0.1.0.test")
    properties = ET.SubElement(artifact, "properties", size="5")
    for name, value in package._artifact_values(jar).items():
        ET.SubElement(properties, "property", name=name, value=value)
    xml = ET.tostring(tree, encoding="utf-8")
    with zipfile.ZipFile(root / "artifacts.jar", "w") as archive:
        archive.writestr("artifacts.xml", xml)
    (root / "artifacts.xml.xz").write_bytes(lzma.compress(xml))
    (root / "content.jar").write_bytes(b"unchanged native version/dependency metadata")
    return jar, members


def test_portable_native_site_preserves_payloads_licenses_and_all_p2_checksums(tmp_path):
    jar, original = native_site_fixture(tmp_path)
    content_before = (tmp_path / "content.jar").read_bytes()
    assert package.portable_update_site(tmp_path) == [jar.name]
    with zipfile.ZipFile(jar) as archive:
        for name, data in original.items():
            if name != "conda_licenses/metadata_licenses.txt":
                assert archive.read(name) == data
        report = archive.read("conda_licenses/metadata_licenses.txt")
        assert report == b"Other package: BSD\nfxmacrodata_public_client-0.1.0-py3-none-any.whl: UNKNOWN\n"
    with zipfile.ZipFile(tmp_path / "artifacts.jar") as archive:
        xml = archive.read("artifacts.xml")
    assert lzma.decompress((tmp_path / "artifacts.xml.xz").read_bytes()) == xml
    values = {p.get("name"): p.get("value") for p in ET.fromstring(xml).findall("./artifacts/artifact/properties/property")}
    data = jar.read_bytes()
    assert values["artifact.size"] == values["download.size"] == str(len(data))
    for label, algorithm in [("sha-1", "sha1"), ("sha-256", "sha256"), ("sha-512", "sha512")]:
        assert values["download.checksum." + label] == hashlib.new(algorithm, data).hexdigest()
    assert (tmp_path / "content.jar").read_bytes() == content_before
    before = jar.read_bytes()
    assert package.portable_update_site(tmp_path) == []
    assert jar.read_bytes() == before


def test_portable_native_site_refuses_signed_jars(tmp_path):
    jar, _ = native_site_fixture(tmp_path, signed=True)
    before = jar.read_bytes()
    with pytest.raises(ValueError, match="signed"):
        package.portable_update_site(tmp_path)
    assert jar.read_bytes() == before


def test_portable_license_metadata_preserves_license_classification_and_rejects_ambiguity():
    assert package._portable_license_metadata(b"/temporary/build/package: UNKNOWN\r\n", ["fixture.whl"]) == b"fixture.whl: UNKNOWN\r\n"
    with pytest.raises(ValueError):
        package._portable_license_metadata(b"/temporary/build/package: MIT\n", ["fixture.whl"])
    with pytest.raises(ValueError):
        package._portable_license_metadata(b"/temporary/build/package: UNKNOWN\n", ["one.whl", "two.whl"])
    for prefix in (b"C:/temporary/build", b"C:\\\\temporary\\\\build", b"file:///C:/temporary/build", b"C%3A%5Ctemporary%5Cbuild", b"file%3A%2F%2F%2Ftemporary%2Fbuild"):
        assert package._portable_license_metadata(prefix + b": UNKNOWN\n", ["fixture.whl"]) == b"fixture.whl: UNKNOWN\n"


def test_portable_site_rejects_inconsistent_indexes_before_changing_jars(tmp_path):
    jar, _ = native_site_fixture(tmp_path)
    before = jar.read_bytes()
    (tmp_path / "artifacts.xml.xz").write_bytes(lzma.compress(b"<different/>"))
    with pytest.raises(ValueError, match="indexes disagree"):
        package.portable_update_site(tmp_path)
    assert jar.read_bytes() == before
