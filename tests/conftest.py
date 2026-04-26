"""pytest config: ensure project root is importable so tests can `import main`."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
