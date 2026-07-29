"""Repo-root anchor.

Every script that resolves paths against the repository root imports PROJECT_ROOT from
here rather than counting `Path(__file__).parent` hops of its own. Counting hops breaks
silently whenever a file moves between directories — and it breaks in a way tests often
miss, because tests tend to patch PROJECT_ROOT with a tmp_path instead of exercising the
real value.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
