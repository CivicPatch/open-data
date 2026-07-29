from scripts.jurisdictions.scrapers import co as co_scraper
from scripts.jurisdictions.scrapers import ma as ma_scraper
from scripts.jurisdictions.scrapers import me as me_scraper
from scripts.jurisdictions.scrapers import mi as mi_scraper
from scripts.jurisdictions.scrapers import nc as nc_scraper
from scripts.jurisdictions.scrapers import nh as nh_scraper
from scripts.jurisdictions.scrapers import nj as nj_scraper
from scripts.jurisdictions.scrapers import sc as sc_scraper
from scripts.jurisdictions.scrapers import tn as tn_scraper
from scripts.jurisdictions.scrapers import tx as tx_scraper
from scripts.jurisdictions.scrapers import wa as wa_scraper

# Add a new state here to enable setup_local.py / setup_counties.py, maps, and validation for it.
# Keys:
#   fips               — US Census FIPS code for the state
#   name               — full state name; builds Wikipedia page titles
#                        (e.g. "List_of_counties_in_North_Carolina")
#   pull_from_census   — "places" and/or "county_subdivisions"
#   scraper            — module in scripts/scrapers/ with a scrape(census_data) function
#   validation_sources — list of external sources to transform; "google" is standard,
#                        additional sources (e.g. "tml") are state-specific opt-ins

state_configs = {
    "co": {
        "fips": "08",
        "name": "Colorado",
        "pull_from_census": ["places"],
        "scraper": co_scraper,
        "validation_sources": ["google"],
    },
    "ma": {
        "fips": "25",
        "name": "Massachusetts",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": ma_scraper,
        "validation_sources": ["google"],
    },
    "me": {
        "fips": "23",
        "name": "Maine",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": me_scraper,
        "validation_sources": ["google"],
    },
    "mi": {
        "fips": "26",
        "name": "Michigan",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": mi_scraper,
        "validation_sources": ["google"],
    },
    "nc": {
       "fips": "37",
       "name": "North Carolina",
       "pull_from_census": ["places"],
       "scraper": nc_scraper,
       "validation_sources": ["google"],
    },
    "nh": {
        "fips": "33",
        "name": "New Hampshire",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": nh_scraper,
        "validation_sources": ["google"],
    },
    "nj": {
        "fips": "34",
        "name": "New Jersey",
        "pull_from_census": ["places", "county_subdivisions"],
        "scraper": nj_scraper,
        "validation_sources": ["google"],
    },
    "sc": {
        "fips": "45",
        "name": "South Carolina",
        "pull_from_census": ["places"],
        "scraper": sc_scraper,
        "validation_sources": ["google"],
    },
    "tn": {
        "fips": "47",
        "name": "Tennessee",
        "pull_from_census": ["places"],
        "scraper": tn_scraper,
        "validation_sources": ["google"],
    },
    "tx": {
        "fips": "48",
        "name": "Texas",
        "pull_from_census": ["places"],
        "scraper": tx_scraper,
        "validation_sources": ["google", "tml"],  # tml = Texas Municipal League
    },
    "wa": {
        "fips": "53",
        "name": "Washington",
        "pull_from_census": ["places"],
        "scraper": wa_scraper,
        "validation_sources": ["google"],
    },
}
