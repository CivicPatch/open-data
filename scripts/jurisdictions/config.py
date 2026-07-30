
# Add a new state here to enable setup_local.py / setup_counties.py, maps, and validation for it.
# Keys:
#   fips               — US Census FIPS code for the state
#   name               — full state name; builds Wikipedia page titles
#                        (e.g. "List_of_counties_in_North_Carolina")
#   pull_from_census   — "places" and/or "county_subdivisions"
#   local_wiki         — municipality list-page overrides: table_index, rows_to_skip,
#                        entry_column, title, parser. {} means all defaults.
#   validation_sources — list of external sources to transform; "google" is standard,
#                        additional sources (e.g. "tml") are state-specific opt-ins

state_configs = {
    "co": {
        "fips": "08",
        "name": "Colorado",
        "pull_from_census": ["places"],
        "local_wiki": {"table_index": 1, "rows_to_skip": 2},
        "validation_sources": ["google"],
    },
    "ga": {
        "fips": "13",
        "name": "Georgia",
        "pull_from_census": ["places"],
        # "List_of_municipalities_in_Georgia" is a disambiguation page (the country vs
        # the U.S. state), so the conventional title has to be overridden here.
        # rows_to_skip 2: two-row header, land area splits into sq mi / km².
        "local_wiki": {
            "title": "List_of_municipalities_in_Georgia_(U.S._state)",
            "rows_to_skip": 2,
        },
        "validation_sources": ["google"],
    },
    "ma": {
        "fips": "25",
        "name": "Massachusetts",
        "pull_from_census": ["places", "county_subdivisions"],
        "local_wiki": {},
        "validation_sources": ["google"],
    },
    "me": {
        "fips": "23",
        "name": "Maine",
        "pull_from_census": ["places", "county_subdivisions"],
        # two-row header: land area splits into sq mi / km²
        "local_wiki": {"rows_to_skip": 2},
        "validation_sources": ["google"],
    },
    "mi": {
        "fips": "26",
        "name": "Michigan",
        "pull_from_census": ["places", "county_subdivisions"],
        "local_wiki": {"rows_to_skip": 2},
        "validation_sources": ["google"],
    },
    "nc": {
       "fips": "37",
       "name": "North Carolina",
       "pull_from_census": ["places"],
       # no full wikitable; municipalities are per-letter bullet lists
       "local_wiki": {"parser": "bullet_list"},
       "validation_sources": ["google"],
    },
    "nh": {
        "fips": "33",
        "name": "New Hampshire",
        "pull_from_census": ["places", "county_subdivisions"],
        "local_wiki": {},
        "validation_sources": ["google"],
    },
    "nj": {
        "fips": "34",
        "name": "New Jersey",
        "pull_from_census": ["places", "county_subdivisions"],
        "local_wiki": {"rows_to_skip": 2},
        "validation_sources": ["google"],
    },
    "sc": {
        "fips": "45",
        "name": "South Carolina",
        "pull_from_census": ["places"],
        "local_wiki": {"rows_to_skip": 2},
        "validation_sources": ["google"],
    },
    "tn": {
        "fips": "47",
        "name": "Tennessee",
        "pull_from_census": ["places"],
        "local_wiki": {},
        "validation_sources": ["google"],
    },
    "tx": {
        "fips": "48",
        "name": "Texas",
        "pull_from_census": ["places"],
        "local_wiki": {"rows_to_skip": 2, "entry_column": 1},
        "validation_sources": ["google", "tml"],  # tml = Texas Municipal League
    },
    "wa": {
        "fips": "53",
        "name": "Washington",
        "pull_from_census": ["places"],
        "local_wiki": {"table_index": 1, "rows_to_skip": 2},
        "validation_sources": ["google"],
    },
}
