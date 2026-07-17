"""Legacy build helper — brand assets are no longer generated or shipped.

Agencies upload Chronos logo + department logo/photo in Chronos UI
(Branding & Media). Builds must not bake Dodgeville/sample images.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "generate_assets: skipped — no logo.png/team_photo.jpg shipped. "
        "Upload branding in Chronos → Branding & Media after install."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
