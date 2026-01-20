from typing import List, Optional
from pydantic import BaseModel, field_validator, model_validator, computed_field
import re
from urllib.parse import urlparse
from datetime import datetime, timezone

class Jurisdiction(BaseModel):
    id: str
    name: str  # Common name of the jurisdiction (including lsad)
    url: Optional[str] = None
    population: Optional[int] = (
        None  # This might be under divisions -> meta; consult repo
    )
    geoid: Optional[str] = None  # This is definitely under divisions somewhere

class Office(BaseModel):
    name: str
    division_ocdid: Optional[str] = None 

class Official(BaseModel):
    name: str
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    office: Office = None
    image: Optional[str] = None
    jurisdiction_ocdid: str
    cdn_image: Optional[str] = None
    source_urls: List[str]
    updated_at: str

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v):
        if v is None:
            return v
        patterns = [
            r"^\d{4}$",
            r"^\d{4}-\d{2}$",
            r"^\d{4}-\d{2}-\d{2}$",
        ]
        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError("Start date must be in format YYYY, YYYY-MM, or YYYY-MM-DD")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v):
        if v is None:
            return v
        patterns = [
            r"^\d{4}$",
            r"^\d{4}-\d{2}$",
            r"^\d{4}-\d{2}-\d{2}$",
        ]
        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError("End date must be in format YYYY, YYYY-MM, or YYYY-MM-DD")
        return v

    @field_validator("phones")
    @classmethod
    def validate_phones(cls, v):
        phone_pattern = r"^\(\d{3}\) \d{3}-\d{4}( ext\. ?\d+)?$"
        for phone in v:
            if not re.match(phone_pattern, phone):
                raise ValueError(
                    f"Phone number must be in format '(XXX) XXX-XXXX' or '(XXX) XXX-XXXX ext.XXX', got: '{phone}'"
                )
        return v

    @field_validator("emails")
    @classmethod
    def validate_emails(cls, v):
        email_pattern = r"^[^@]+@[^@]+$"
        for email in v:
            if not re.match(email_pattern, email):
                raise ValueError(f"Email must be in format 'anything@anything', got: '{email}'")
        return v

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v):
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"Website must start with 'http://' or 'https://', got: '{url}'"
                )
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                raise ValueError(f"Website must be a valid URL with a domain, got: '{url}'")
        return v

    @field_validator("updated_at")
    @classmethod
    def validate_updated_at(cls, v):
        datetime_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
        if not re.match(datetime_pattern, v):
            expected_format = datetime.now(timezone.utc).isoformat(timespec="seconds")
            raise ValueError(f"DateTime must be in format '{expected_format}', got: '{v}'")
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"Invalid datetime value: '{v}'")
        return v

    @field_validator("source_urls")
    @classmethod
    def validate_source_urls(cls, v):
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(
                    f"Source URL must start with 'http://' or 'https://', got: '{url}'"
                )
            parsed = urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                raise ValueError(f"Source URL must be a valid URL with a domain, got: '{url}'")
        return v

# Old schema for reference
#class Person(BaseModel):
#    jurisdiction_ocdid: str
#    name: str
#    roles: List[str]
#    divisions: List[str]
#    phone_number: Optional[str] = None
#    email: Optional[str] = None
#    website: Optional[str] = None
#    start_date: Optional[str] = None
#    end_date: Optional[str] = None
#    image: Optional[str] = None
#    cdn_image: Optional[str] = None
#    sources: List[str]  # List of source URLs where information was found
#    updated_at: str
#
#    @model_validator(mode="before")
#    def convert_empty_strings_to_null(cls, values):
#        # Iterate through all fields and convert '' to None
#        return {key: (None if value == "" else value) for key, value in values.items()}
#
#    @field_validator("phone_number")
#    @classmethod
#    def validate_phone_number(cls, v):
#        if v is None:
#            return v
#
#        # Allow extensions in the format '(XXX) XXX-XXXX' or '(XXX) XXX-XXXX ext.XXX' with optional space after 'ext.'
#        phone_pattern = r"^\(\d{3}\) \d{3}-\d{4}( ext\. ?\d+)?$"
#
#        if not re.match(phone_pattern, v):
#            raise ValueError(
#                f"Phone number must be in format '(XXX) XXX-XXXX' or '(XXX) XXX-XXXX ext.XXX', got: '{v}'"
#            )
#
#        return v
#
#    @field_validator("email")
#    @classmethod
#    def validate_email(cls, v):
#        if v is None:
#            return v
#
#        # Check basic email format: anything@anything
#        email_pattern = r"^[^@]+@[^@]+$"
#
#        if not re.match(email_pattern, v):
#            raise ValueError(f"Email must be in format 'anything@anything', got: '{v}'")
#
#        return v
#
#    @field_validator("website")
#    @classmethod
#    def validate_website(cls, v):
#        if v is None:
#            return v
#
#        # Must start with http:// or https://
#        if not v.startswith(("http://", "https://")):
#            raise ValueError(
#                f"Website must start with 'http://' or 'https://', got: '{v}'"
#            )
#
#        # Parse and validate domain
#        parsed = urlparse(v)
#        if not parsed.netloc or "." not in parsed.netloc:
#            raise ValueError(f"Website must be a valid URL with a domain, got: '{v}'")
#
#        return v
#
#    @field_validator("start_date")
#    @classmethod
#    def validate_start_date(cls, v):
#        if v is None:
#            return v
#
#        # Valid patterns: YYYY, YYYY-MM, YYYY-MM-DD
#        patterns = [
#            r"^\d{4}$",  # YYYY
#            r"^\d{4}-\d{2}$",  # YYYY-MM
#            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
#        ]
#
#        if not any(re.match(pattern, v) for pattern in patterns):
#            raise ValueError(
#                f"Start date must be in format YYYY, YYYY-MM, or YYYY-MM-DD"
#            )
#
#        return v
#
#    @field_validator("end_date")
#    @classmethod
#    def validate_end_date(cls, v):
#        if v is None:
#            return v
#
#        # Valid patterns: YYYY, YYYY-MM, YYYY-MM-DD
#        patterns = [
#            r"^\d{4}$",  # YYYY
#            r"^\d{4}-\d{2}$",  # YYYY-MM
#            r"^\d{4}-\d{2}-\d{2}$",  # YYYY-MM-DD
#        ]
#
#        if not any(re.match(pattern, v) for pattern in patterns):
#            raise ValueError(f"End date must be in format YYYY, YYYY-MM, or YYYY-MM-DD")
#
#        return v
#
#    @field_validator("updated_at")
#    @classmethod
#    def validate_updated_at(cls, v):
#        # Must be in exact format: YYYY-MM-DDTHH:MM:SS+00:00 (or other timezone)
#        datetime_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
#
#        if not re.match(datetime_pattern, v):
#            expected_format = datetime.now(timezone.utc).isoformat(timespec="seconds")
#            raise ValueError(
#                f"DateTime must be in format '{expected_format}', got: '{v}'"
#            )
#
#        # Try to parse to ensure it's a valid datetime
#        try:
#            datetime.fromisoformat(v)
#        except ValueError:
#            raise ValueError(f"Invalid datetime value: '{v}'")
#
#        return v
#