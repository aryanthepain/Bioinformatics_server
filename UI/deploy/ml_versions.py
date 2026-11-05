"""Print the version of one package pinned in uv.lock (used by deploy/Dockerfile).

    python ml_versions.py path/to/uv.lock torch     ->  2.14.1
"""

import sys
import tomllib

lock_path, name = sys.argv[1], sys.argv[2]
with open(lock_path, "rb") as handle:
    lock = tomllib.load(handle)
versions = [package["version"] for package in lock.get("package", []) if package.get("name") == name]
if not versions:
    sys.exit(f"{name} is not in {lock_path}")
print(versions[0])
