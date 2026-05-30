#!/usr/bin/env python3
"""Convenience entrypoint so the app can be run as `python x.py ...`.

Equivalent to `python -m air_monitor ...`. The package uses relative imports,
so we add the parent directory to sys.path and import it as a package.

Examples:
    python x.py run
    python x.py serve --port 9000
    python x.py collect-once
    python x.py init-db
"""

import os
import sys

_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from air_monitor.main import main

if __name__ == "__main__":
    raise SystemExit(main())
