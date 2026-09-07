"""Prove the frozen EXE carries the three fixes, by unpacking its own PYZ.

PyInstaller stores modules zlib-compressed inside the archive, so grepping the
raw EXE finds nothing. This reads the real archive through PyInstaller's own
reader, decompiles nothing, and just checks the marshalled code objects for the
constants and names each fix introduced.
"""
import marshal
import sys

from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

EXE = "dist/ProTube.exe"

CHECKS = {
    "src.core.engine": [
        "tlang=",          # transcript translation split
        "is_translation",
        "_requires_auth_retry",  # download() now gates the cookie fallback
    ],
    "src.core.models": ["is_translation", "auto-translated"],
    "src.core.download_options": ["resolve_best_audio_format_id", "DOWNLOAD_MODE_TEXT"],
}


def walk(code, out):
    """Collect every name and string constant reachable from a code object."""
    out.update(code.co_names)
    out.update(code.co_varnames)
    for const in code.co_consts:
        if isinstance(const, str):
            out.add(const)
        elif hasattr(const, "co_code"):
            walk(const, out)


carchive = CArchiveReader(EXE)
pyz_name = next(n for n in carchive.toc if n.endswith(".pyz") or n == "PYZ-00.pyz")
pyz_data = carchive.extract(pyz_name)

with open("_pyz_tmp.pyz", "wb") as fh:
    fh.write(pyz_data)
pyz = ZlibArchiveReader("_pyz_tmp.pyz")

failures = []
for module, markers in CHECKS.items():
    try:
        # PyInstaller changed this API across versions: older releases return
        # (is_pkg, marshalled_bytes), newer ones return the code object itself.
        entry = pyz.extract(module)
    except Exception as exc:  # module missing from the archive entirely
        failures.append(f"{module}: NOT IN EXE ({exc})")
        continue
    if isinstance(entry, tuple):
        entry = entry[1]
    code = entry if hasattr(entry, "co_code") else marshal.loads(entry)
    strings = set()
    walk(code, strings)
    for marker in markers:
        hit = any(marker in s for s in strings)
        print(f"  {module:30} {marker:26} {'FOUND' if hit else 'MISSING'}")
        if not hit:
            failures.append(f"{module}:{marker}")

print()
if failures:
    print("FAIL:", failures)
    sys.exit(1)
print("PASS: every fix is present in the frozen EXE")
