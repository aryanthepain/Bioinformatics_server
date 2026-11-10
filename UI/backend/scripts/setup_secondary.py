"""One-time set-up of the secondary-structure level: the notebook's set-up cell.

From the backend folder, after `uv sync` (needs the internet, git, make and a C
compiler - on a Mac: xcode-select --install):

    uv run python scripts/setup_secondary.py

It does what the first cell of "SecondaryStructureFinal.ipynb" does, except installing
the Python packages, which `uv sync` already did (gor4, the GOR IV C code, is pinned to
the same commit in pyproject.toml):

  * S4PRED and PSIPRED source code, at the notebook's pinned commits;
  * PSIPRED's seq2mtx, psipred and psipass2, built with make;
  * the first S4PRED checkpoint (about 83 MB compressed), checked against its SHA-256
    (or, with S4PRED_FULL_ENSEMBLE, the whole 413 MB archive against its MD5);
  * the ESM-2 secondary-structure checkpoint (31 MB) at its pinned revision.

Everything goes into backend/data/secondary (or PFP_SECONDARY_DATA_DIR, or --assets),
which git ignores. Running it again only downloads what is missing. The Docker image
runs it while it is built (deploy/Dockerfile).
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from time import perf_counter
from urllib.request import urlopen

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ASSETS = Path(os.getenv("PFP_SECONDARY_DATA_DIR", "").strip() or BACKEND_DIR / "data" / "secondary")

# The notebook's cell 0 (app/levels/secondary.py uses the same values).
ESM_ID = "AmelieSchreiber/esm2_t6_8M_UR50D-finetuned-secondary-structure"
ESM_REVISION = "24b37e9d0341861d4c0e675ee771990d5a519b90"
S4PRED_FULL_ENSEMBLE = False  # True downloads the entire 413 MB archive.
SOURCES = {
    "s4pred": ("https://github.com/psipred/s4pred.git", "7f309dfc9a8155efdf30113fb4cb0affb40aeb7e"),
    "psipred": ("https://github.com/psipred/psipred.git", "aba0c2a0caf88174c59959ee3fd0466da235eec9"),
}
S4PRED_URL = "https://bioinf.cs.ucl.ac.uk/downloads/s4pred/weights.tar.gz"
S4PRED_ARCHIVE_MD5 = "e04ad7d10b61551f7e07a86b65bb88dc"
S4PRED_WEIGHTS_1_SHA256 = "3776a95c56fe49fda9e07692501dcb01a4f0e88aba94a6d39eaa2ec9999e8ee7"


def setup(ASSETS: Path) -> None:
    setup_started = perf_counter()

    ASSETS.mkdir(parents=True, exist_ok=True)

    for folder, (repo, commit) in SOURCES.items():
        checkout = ASSETS / folder
        if not checkout.exists():
            print(f"Fetching {folder} at {commit[:12]}...", flush=True)
            with tempfile.TemporaryDirectory(dir=ASSETS) as scratch:
                staged = Path(scratch) / folder
                subprocess.run(["git", "init", "-q", str(staged)], check=True)
                subprocess.run(["git", "-C", str(staged), "fetch", "-q", "--depth=1", repo, commit], check=True)
                subprocess.run(["git", "-C", str(staged), "checkout", "-q", "FETCH_HEAD"], check=True)
                staged.rename(checkout)

    print("Building PSIPRED (seq2mtx, psipred, psipass2)...", flush=True)
    subprocess.run(["make", "-C", str(ASSETS / "psipred" / "src"),
                    "seq2mtx", "psipred", "psipass2"], check=True)

    weight_dir = ASSETS / "s4pred" / "weights"
    weight_names = {f"weights_{i}.pt" for i in range(1, 6)} if S4PRED_FULL_ENSEMBLE else {"weights_1.pt"}
    if not all((weight_dir / name).is_file() for name in weight_names):
        url = S4PRED_URL
        with tempfile.TemporaryDirectory(dir=ASSETS) as scratch:
            staged = Path(scratch)
            if S4PRED_FULL_ENSEMBLE:
                print("Downloading the full S4PRED ensemble (413 MB)...", flush=True)
                archive_path = staged / "weights.tar.gz"
                digest = hashlib.md5()  # Compare with the model authors' published checksum.
                with urlopen(url, timeout=60) as response, archive_path.open("wb") as output:
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        output.write(chunk)
                        digest.update(chunk)
                if digest.hexdigest() != S4PRED_ARCHIVE_MD5:
                    raise RuntimeError("S4PRED archive does not match the published checksum.")
                with tarfile.open(archive_path) as archive:
                    for member in archive.getmembers():
                        name = Path(member.name).name
                        if member.isfile() and name in weight_names:
                            with archive.extractfile(member) as source, (staged / name).open("wb") as output:
                                shutil.copyfileobj(source, output)
            else:
                print("Downloading the first S4PRED checkpoint (about 83 MB compressed)...", flush=True)
                checkpoint = staged / "weights_1.pt"
                with urlopen(url, timeout=60) as response, tarfile.open(fileobj=response, mode="r|gz") as archive:
                    for member in archive:
                        if member.isfile() and Path(member.name).name == checkpoint.name:
                            with archive.extractfile(member) as source, checkpoint.open("wb") as output:
                                shutil.copyfileobj(source, output)
                            break
                if not checkpoint.is_file() or hashlib.sha256(checkpoint.read_bytes()).hexdigest() != (
                    S4PRED_WEIGHTS_1_SHA256
                ):
                    raise RuntimeError("The S4PRED checkpoint does not match the expected SHA-256.")
            weight_dir.mkdir(exist_ok=True)
            for name in sorted(weight_names):
                (staged / name).replace(weight_dir / name)

    print("Checking the ESM-2 checkpoint cache (31 MB on first download)...", flush=True)
    subprocess.run([
        sys.executable, "-c",
        "import sys; from huggingface_hub import snapshot_download; "
        "snapshot_download(sys.argv[1], revision=sys.argv[2], cache_dir=sys.argv[3], "
        "allow_patterns=['config.json', 'tokenizer_config.json', 'special_tokens_map.json', "
        "'vocab.txt', 'model.safetensors'])",
        ESM_ID, ESM_REVISION, str(ASSETS / "hf"),
    ], check=True)
    print(f"Setup finished in {perf_counter() - setup_started:.1f} s.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help=f"target folder (default: {DEFAULT_ASSETS})")
    args = parser.parse_args()
    missing = [tool for tool in ("git", "make") if shutil.which(tool) is None]
    if missing:
        print("Missing: " + ", ".join(missing) + ". On a Mac run: xcode-select --install")
        return 1
    try:
        setup(args.assets.resolve())
    except subprocess.CalledProcessError as error:
        print(f"\nFAILED: {' '.join(str(part) for part in error.cmd[:4])}… exited with {error.returncode}")
        return 1
    except (OSError, RuntimeError) as error:
        print(f"\nFAILED: {error}")
        return 1
    print(f"The secondary-structure assets are in {args.assets.resolve()}.")
    print("Check them against the notebook with: uv run python scripts/check_secondary.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
