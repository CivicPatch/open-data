"""Tables ported from scripts/country-us/census_places.py in opencivicdata/ocd-division-ids."""

# "prefix": county subdivisions are strictly within counties, so the ID carries the county
# (county:X/place:Y). "town": they are the equivalent of places (place:Y).
SUBDIV_RULES = {
    "ct": "town", "ma": "town", "me": "town", "nh": "town", "ri": "town", "vt": "town",
    "il": "prefix", "in": "prefix", "ks": "prefix", "mi": "prefix", "mn": "prefix",
    "mo": "prefix", "nd": "prefix", "ne": "prefix", "nj": "prefix", "ny": "prefix",
    "oh": "prefix", "pa": "prefix", "sd": "prefix", "wi": "prefix",
}

# Tried in order. " CDP" is ours: the registry skips CDPs, but a newly incorporated place
# can keep its CDP name for a Census vintage.
PLACE_ENDINGS = (" municipality", " borough", " city", " town", " village", " CDP")
SUBDIVISION_ENDINGS = (" town", " village", " township", " plantation")
COUNTY_ENDINGS = {
    " County": "county",
    " Parish": "parish",
    " Borough": "borough",
    " Municipality": "borough",
    " Census Area": "census_area",
    " Municipio": "municipio",
}

PLACE_NAME_OVERRIDES = {
    "Wrangell city and borough": "Wrangell",
    "Sitka city and borough": "Sitka",
    "Juneau city and borough": "Juneau",
    "Lexington-Fayette urban county": "Lexington",
    "Lynchburg, Moore County metropolitan government": "Lynchburg",
    "Cusseta-Chattahoochee County unified government": "Cusseta",
    "Georgetown-Quitman County unified government": "Georgetown",
    "Anaconda-Deer Lodge County": "Anaconda",
    "Hartsville/Trousdale County": "Hartsville",
    "Webster County unified government": "Webster County ",
    "Ranson corporation": "Ranson",
    "Carson City": "Carson City",
    "Princeton": "Princeton",
}

# Same-named places in one state, told apart by county.
PLACE_GEOID_OVERRIDES = {
    "2756680": "St. Anthony (Hennepin/Ramsey Counties)",
    "2756698": "St. Anthony (Stearns County)",
    "4861592": "Reno (Lamar County)",
    "4861604": "Reno (Parker County)",
    "4840738": "Lakeside (San Patricio County)",
    "4840744": "Lakeside (Tarrant County)",
    "4853154": "Oak Ridge (Cooke County)",
    "4853160": "Oak Ridge (Kaufman County)",
    "4253336": "Newburg borough (Clearfield County)",
    "4253344": "Newburg borough (Cumberland County)",
    "4214584": "Coaldale borough (Bedford County)",
    "4214600": "Coaldale borough (Schuylkill County)",
    "4243064": "Liberty borough (Allegheny County)",
    "4243128": "Liberty borough (Tioga County)",
    "4261496": "Pleasantville borough (Bedford County)",
    "4261512": "Pleasantville borough (Venango County)",
    "4237880": "Jefferson borough (Greene County)",
    "4237944": "Jefferson borough (York County)",
    "4212184": "Centerville borough (Crawford County)",
    "4212224": "Centerville borough (Washington County)",
}

COUNTY_NAME_OVERRIDES = {
    "Wrangell City and Borough": ("Wrangell", "borough"),
    "Sitka City and Borough": ("Sitka", "borough"),
    "Juneau City and Borough": ("Juneau", "borough"),
    "Yakutat City and Borough": ("Yakutat", "borough"),
}
