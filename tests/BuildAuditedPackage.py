"""Stage a matched flat-Skyrim build in this checkout and create a new FOMOD ZIP.

Usage: python tests/BuildAuditedPackage.py NATIVE_REPO NATIVE_BUILD PEX_OUTPUT ZIP
Only this checkout and the new ZIP are written. No game/Vortex/save paths are used.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

root = Path(__file__).resolve().parents[1]
native, build, pex, archive = (Path(p).resolve() for p in sys.argv[1:])
assert not archive.exists(), "Refusing to replace an existing archive"
cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
for key in ("ENABLE_SKYRIM_VR", "INTELENGINE_ENABLE_VR"):
    setting = next(line.split("=", 1)[1].lower() for line in cache.splitlines() if line.startswith(key + ":"))
    assert setting in ("0", "off", "false", "no"), "VR-enabled build refused"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    assert sha(source) == sha(destination)

def copy_tree(source, destination):
    files = [p for p in source.rglob("*") if p.is_file()]
    assert files, f"Empty source: {source}"
    existing = {p.relative_to(destination) for p in destination.rglob("*") if p.is_file()}
    wanted = {p.relative_to(source) for p in files}
    assert existing <= wanted, f"Stale files require review in {destination}"
    for path in files:
        copy_file(path, destination / path.relative_to(source))

def anonymous_pex(data):
    # Skyrim PEX uses big-endian fields; three length-prefixed diagnostic strings
    # follow the 16-byte fixed header. Keep source basename, remove user/host only.
    assert data[:8] == bytes.fromhex("fa57c0de03020001"), "Unexpected PEX format"
    offset, strings = 16, []
    for _ in range(3):
        length = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        strings.append(data[offset:offset + length])
        offset += length
    assert b"/" not in strings[0] and b"\\" not in strings[0]
    return data[:16] + b"".join(struct.pack(">H", len(s)) + s for s in (strings[0], b"builder", b"build-host")) + data[offset:]

compiled = json.loads((pex / "compile-manifest.json").read_text(encoding="utf-8-sig"))
story = (native / "Source/Scripts/IntelEngine_StoryEngine.psc").read_text(encoding="utf-8")
assert "Bool Function AllStoryTypesExcluded(String excludeList)" in story
assert "If AllStoryTypesExcluded(excludeList)" in story, "Missing game-dev all-types-disabled guard"
expected = {p.name for p in (native / "Source/Scripts").glob("IntelEngine*.psc")} | {"QF_IntelEngine_02000D61.psc"}
assert len(compiled) == 11 and {e["Source"] for e in compiled} == expected
for entry in compiled:
    source = (root if entry["Source"].startswith("QF_") else native) / "Source/Scripts" / entry["Source"]
    assert sha(source) == entry["SourceSHA256"].lower(), "Source changed after compilation"
    output = pex / entry["Output"]
    assert sha(output) == entry["OutputSHA256"].lower(), "PEX changed after compilation"
    if not entry["Source"].startswith("QF_"):
        copy_file(source, root / "Source/Scripts" / source.name)
    (root / "Scripts" / output.name).write_bytes(anonymous_pex(output.read_bytes()))

copy_file(build / "IntelEngine.dll", root / "SKSE/Plugins/IntelEngine.dll")
copy_tree(native / "SKSE/Plugins/SkyrimNet/external/galanx.intelengine", root / "SKSE/Plugins/SkyrimNet/external/galanx.intelengine")
copy_tree(native / "SKSE/Plugins/SkyrimNet/config/plugins/IntelEngine", root / "SKSE/Plugins/SkyrimNet/config/plugins/IntelEngine")
copy_tree(native / "web/dashboard/dist", root / "PrismaUI/views/IntelEngine/dashboard")
migration = build.parent / "build-migration-flat"
copy_file(migration / "LegacyCacheMigration.exe", root / "IntelEngineTools/LegacyCacheMigration.exe")
copy_file(native / "SKSE/migration/Convert-IE-Save.bat", root / "IntelEngineTools/Convert-IE-Save.bat")

for element in ET.parse(root / "fomod/ModuleConfig.xml").iter():
    if "source" in element.attrib:
        assert (root / element.attrib["source"].replace("\\", "/")).exists(), "Broken FOMOD reference"

dirs = ("fomod", "Scripts", "Source", "Interface", "SKSE", "PrismaUI", "IntelEngineTools")
files = [root / name for name in ("IntelEngine.esp", "README.md", "FAQ.md", "CHANGELOG.md")]
files += [p for name in dirs for p in (root / name).rglob("*") if p.is_file()]
assert all(p.suffix.lower() not in (".pdb", ".ess", ".skse", ".log", ".sqlite", ".db") for p in files)
assert not any("vrik" in p.name.lower() or p.name.lower() == "openvr_api.dll" for p in files)
manifest = {
    "variant": "3.6.0-dev-gts118-flat.2",
    "native_upstream": "Gerkinfeltser/IntelEngine-NativePlugin@6c32c8aef8823b5e1d8553d56870b9ce485fbfee",
    "game_upstream": "Gerkinfeltser/IntelEngine-GamePlugin@83f4dbfb4aff4be363142a35350c5aaacc06b1d9",
    "native_commit": subprocess.check_output(["git", "-C", str(native), "rev-parse", "HEAD"], text=True).strip(),
    "vr_enabled": False,
    "pex_metadata": "Only diagnostic user/host strings anonymized; bytecode unchanged.",
    "files": {p.relative_to(root).as_posix(): sha(p) for p in sorted(files)},
}
manifest_path = root / "package-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
files += [manifest_path, root / "docs/FLAT-TRIAL.md"]
archive.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as z:
    for path in files:
        z.write(path, path.relative_to(root).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(name)).hexdigest() == digest for name, digest in manifest["files"].items())
print(f"PASS: {len(files)} files, 11 matching PEX, complete FOMOD, no VR build, archive hashes verified")
print(f"ZIP SHA256: {sha(archive)}")
