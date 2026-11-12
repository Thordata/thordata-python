import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thordata import Client

with Client() as client:
    result = client.search(
        {"q": "latest AI agent research", "gl": "us", "hl": "en", "num": 5},
        engine="google_search",
    )
    print(result)
