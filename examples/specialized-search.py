import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thordata import Client

with Client() as client:
    result = client.search(
        {
            "departure_id": "SFO",
            "arrival_id": "JFK",
            "outbound_date": "2026-12-01",
            "return_date": "2026-12-08",
        },
        engine="google_flights",
    )
    print(result)
