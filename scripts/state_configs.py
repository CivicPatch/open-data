from scripts.scrapers import co as co_scraper
from scripts.scrapers import mi as mi_scraper
from scripts.scrapers import nj as nj_scraper
from scripts.scrapers import sc as sc_scraper
from scripts.scrapers import tx as tx_scraper
from scripts.scrapers import wa as wa_scraper

# Add a new state here to enable setup_local.py / setup_counties.py, maps, and validation for it.
# Keys:
#   fips               — US Census FIPS code for the state
#   pull_from_census   — "places" and/or "county_subdivisions"
#   scraper            — module in scripts/scrapers/ with a scrape(census_data) function
#   validation_sources — list of external sources to transform; "google" is standard,
#                        additional sources (e.g. "tml") are state-specific opt-ins

state_configs = {
    "co": {
        "fips": "08",
        "pull_from_census": ["places"],
        "scraper": co_scraper,
        "validation_sources": ["google"],
    },
    "mi": {
        "fips": "26",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": mi_scraper,
        "validation_sources": ["google"],
    },
    "nj": {
        "fips": "34",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": nj_scraper,
        "validation_sources": ["google"],
    },
    "sc": {
        "fips": "45",
        "pull_from_census": ["places"],
        "scraper": sc_scraper,
        "validation_sources": ["google"],
    },
    "tx": {
        "fips": "48",
        "pull_from_census": ["places"],
        "scraper": tx_scraper,
        "validation_sources": ["google", "tml"],  # tml = Texas Municipal League
    },
    "wa": {
        "fips": "53",
        "pull_from_census": ["places"],
        "scraper": wa_scraper,
        "validation_sources": ["google"],
    },
}
