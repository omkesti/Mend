"""pytest bootstrap.

Provides dummy settings so the suite runs without a real `.env` (e.g. on a fresh
clone, or when the agent heals this repo). The tests are pure and never make
real Groq/GitHub calls, so placeholder credentials are fine.
"""

import os

os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")
