from typing import List, Optional

from pydantic import BaseModel


class Jurisdiction(BaseModel):
    id: str
    name: str  # Common name of the jurisdiction (including lsad)
    url: Optional[str] = None
    population: Optional[int] = None
    geoid: Optional[str] = None
    status: Optional[str] = None  # lifecycle: null = active, "inactive" = dropped from census
    wiki_url: Optional[str] = None  # Wikipedia page URL
    generated_comments: Optional[str] = None  # script-generated notes; replaced each run
    issues: Optional[List[str]] = None  # detected problems e.g. ["ocdid_collision"]; replaced each run
    comments: Optional[str] = None  # free-form human notes; NEVER overwritten by scripts
