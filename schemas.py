from typing import List, Optional
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    roles: List[str]
    divisions: List[str]
    phone_number: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    image: Optional[str] = None
    cdn_image: str
    jurisdiction_id: str
    sources: List[str] # List of source URLs where information was found
    updated_at: str
