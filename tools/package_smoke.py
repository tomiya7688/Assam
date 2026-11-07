"""Build the wheel and sdist, install the wheel into a fresh venv, and smoke-test it.

Usage: python tools/package_smoke.py [WORK_DIR]
WORK_DIR defaults to a temporary directory; pass one to keep build output off the system drive.
"""

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DATA = {
    "instruction_registry.json",
    "instruction-registry-v3.schema.json",
    "program-ir-v1.schema.json",
}


def run(*command, cwd=None):
    print("+", " ".join(map(str, command)), flush=True)
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def main(argv):
    work = (
        Path(argv[1])
        if len(argv) > 1
        else Path(tempfile.mkdtemp(prefix="assam-smoke-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    dist = work / "dist"
    # Build from a clean copy: setuptools reuses stale build/ and *.egg-info output in the source tree,
    # which would hide a broken pyproject (for example, missing package data).
    source = work / "source"
    if source.exists():
        shutil.rmtree(source)
    shutil.copytree(
        ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            "build",
            "dist",
            "*.egg-info",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "node_modules",
        ),
    )
    run(sys.executable, "-m", "build", "--outdir", dist, source)
    wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
    assert len(wheels) == 1 and len(sdists) == 1, (
        f"expected one wheel and one sdist in {dist}"
    )

    env_dir = work / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
    bin_dir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    run(python, "-m", "pip", "install", "--no-input", wheels[0])

    # Run from outside the repository so the source tree cannot shadow the installed package.
    probe = (
        "import importlib.resources as r, assam; "
        "names = {p.name for p in (r.files('assam') / 'data').iterdir()}; "
        f"missing = {sorted(REQUIRED_DATA)!r}; "
        "assert set(missing) <= names, (missing, sorted(names)); "
        "assert 'site-packages' in assam.__file__, assam.__file__"
    )
    run(python, "-c", probe, cwd=work)
    run(bin_dir / "assam", "--help", cwd=work)
    result = run(bin_dir / "assam", "run", ROOT / "examples" / "sum.assam", cwd=work)
    assert "42" in result.stdout, result.stdout
    print(f"package smoke OK: {wheels[0].name}, {sdists[0].name}")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr, sep="\n", file=sys.stderr)
        raise
