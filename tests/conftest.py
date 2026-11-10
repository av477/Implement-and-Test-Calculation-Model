"""Shared test setup."""

import os

# Fewer bcrypt rounds keep the test suite fast; production uses the default (12).
# Must be set before app.config is first imported.
os.environ.setdefault("BCRYPT_ROUNDS", "4")
