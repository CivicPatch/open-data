from typing import List, Optional
from pydantic import BaseModel, field_validator
import phonenumbers
from phonenumbers import PhoneNumberFormat, NumberParseException
import re
from urllib.parse import urlparse

class Person(BaseModel):
    jurisdiction_id: str
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
    sources: List[str] # List of source URLs where information was found
    updated_at: str

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is None:
            return v
        
        try:
            # Parse the phone number (assuming US numbers)
            parsed = phonenumbers.parse(v, "US")
            
            # Check if it's a valid number
            if not phonenumbers.is_valid_number(parsed):
                # Try to give more helpful error message
                if phonenumbers.is_possible_number(parsed):
                    raise ValueError(f"Phone number '{v}' is not a valid US number (check area code)")
                else:
                    raise ValueError(f"Phone number '{v}' is not in a valid format")
            
            # Format as (XXX) XXX-XXXX
            formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.NATIONAL)
            return formatted
            
        except NumberParseException as e:
            raise ValueError(f"Could not parse phone number '{v}': {str(e)}")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is None:
            return v
        
        # Simple regex for anything@anything format
        email_pattern = r'^[^@]+@[^@]+$'
        
        if not re.match(email_pattern, v):
            raise ValueError(f"Email '{v}' must be in the format 'anything@anything'")
        
        return v.lower()  # Normalize to lowercase

    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        if v is None:
            return v
        
        # Add https:// if no scheme provided
        if not v.startswith(('http://', 'https://')):
            v = f"https://{v}"
        
        # Parse and validate
        parsed = urlparse(v)
        if not parsed.netloc or '.' not in parsed.netloc:
            raise ValueError(f"Website must be a valid URL with a domain")
        
        return v

    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        if v is None:
            return v
        
        # Valid patterns: YYYY, YYYY/MM, YYYY/MM/DD
        patterns = [
            r'^\d{4}$',                    # YYYY
            r'^\d{4}/\d{2}$',              # YYYY/MM  
            r'^\d{4}/\d{2}/\d{2}$'         # YYYY/MM/DD
        ]
        
        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError(f"Start date must be in format YYYY, YYYY/MM, or YYYY/MM/DD")
        
        return v

    @field_validator('end_date')
    @classmethod
    def validate_end_date(cls, v):
        if v is None:
            return v
        
        # Valid patterns: YYYY, YYYY/MM, YYYY/MM/DD
        patterns = [
            r'^\d{4}$',                    # YYYY
            r'^\d{4}/\d{2}$',              # YYYY/MM  
            r'^\d{4}/\d{2}/\d{2}$'         # YYYY/MM/DD
        ]
        
        if not any(re.match(pattern, v) for pattern in patterns):
            raise ValueError(f"End date must be in format YYYY, YYYY/MM, or YYYY/MM/DD")
        
        return v
