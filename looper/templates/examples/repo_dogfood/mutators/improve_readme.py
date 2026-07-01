from __future__ import annotations

import json
import os
from pathlib import Path

artifact_paths = json.loads(os.environ["LOOPER_ARTIFACTS"])
experiment_index = int(os.environ["LOOPER_EXPERIMENT_INDEX"])
readme_path = Path(artifact_paths[0])

readme = readme_path.read_text(encoding="utf-8")

heading = "## Dogfood Looper On This Repo"
base_section = """## Dogfood Looper On This Repo

Looper can optimize its own README with the reusable dogfood loop in `examples/repo_dogfood/`.

```bash
looper baseline --config examples/repo_dogfood/looper.yaml
looper run --rounds 1 --variants 3 --config examples/repo_dogfood/looper.yaml
looper report --config examples/repo_dogfood/looper.yaml
looper accept best --config examples/repo_dogfood/looper.yaml
```
"""

eval_note = """
The dogfood eval rewards README variants that explain the self-improvement workflow, point to `.looper/reports/latest.md`, and keep the accepted change reviewable.
"""

test_note = """
After accepting a dogfood result, review the diff and run `pytest` before committing or pushing the change.
"""

parts = [base_section, eval_note, test_note]
new_section = "".join(parts[: experiment_index % len(parts) + 1]).rstrip() + "\n"

if heading in readme:
    before, rest = readme.split(heading, 1)
    next_heading = rest.find("\n## ", 1)
    if next_heading == -1:
        readme = before.rstrip() + "\n\n" + new_section
    else:
        readme = before.rstrip() + "\n\n" + new_section + "\n" + rest[next_heading + 1 :].lstrip()
else:
    marker = "## Included Examples"
    if marker not in readme:
        raise SystemExit(f"README marker not found: {marker}")
    before, after = readme.split(marker, 1)
    readme = before.rstrip() + "\n\n" + new_section + "\n" + marker + after

readme_path.write_text(readme, encoding="utf-8")
print(f"updated={readme_path}")
