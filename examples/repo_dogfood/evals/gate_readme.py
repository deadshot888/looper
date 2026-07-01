from __future__ import annotations

from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
lower = readme.lower()

if not readme.startswith("# Looper"):
    raise SystemExit("README must keep the Looper H1.")
if readme.count("## Dogfood Looper On This Repo") > 1:
    raise SystemExit("README must not duplicate the dogfood section.")
if any(secret_word in lower for secret_word in ["password", "api key", "token"]):
    raise SystemExit("README dogfood changes must not mention secrets.")

raise SystemExit(0)
