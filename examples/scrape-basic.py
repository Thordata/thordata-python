import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from thordata import Client

with Client() as client:
    records = client.scrape(
        "linkedin_company_information_by-url",
        {"url": "https://www.linkedin.com/company/microsoft"},
    )
    print(records)
