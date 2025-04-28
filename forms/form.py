from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class FormFieldMetadata:
    """Metadata for a form field"""
    description: str
    field_number: str
    is_boolean: bool = False
    is_multi_select: bool = False
    options: List[str] = field(default_factory=list)
    
    def to_schema_string(self) -> str:
        """Convert field to schema string representation"""
        if self.is_boolean:
            return "boolean"
        elif self.is_multi_select:
            if self.options:
                return f"list[enum[{', '.join(self.options)}]]"
            return "list[string]"
        elif self.options:
            return f"enum[{', '.join(self.options)}]"
        return "string"


@dataclass
class FormMetadataItem:
    """Metadata for non-field form elements"""
    description: str
    location: str
    page: int
    format: Optional[str] = None


@dataclass
class Form:
    """Base class for forms with field metadata organized by page"""
    name: str
    form_number: str
    form_metadata: Dict[str, FormMetadataItem] = field(default_factory=dict)
    fields_by_page: Dict[int, Dict[str, FormFieldMetadata]] = field(default_factory=dict)
    
    @property
    def fields(self) -> Dict[str, FormFieldMetadata]:
        """Get all fields in the form"""
        result = {}
        for page_fields in self.fields_by_page.values():
            result.update(page_fields)
        return result

    def get_fields_for_page(self, page_number: int) -> Dict[str, FormFieldMetadata]:
        """Get all fields that are present on a given page"""
        return self.fields_by_page.get(page_number, {})
    
    def get_field_description(self, field_name: str) -> Optional[str]:
        """Get the description associated with a specific field"""
        for page_fields in self.fields_by_page.values():
            if field_name in page_fields:
                return page_fields[field_name].description
        return None
    
    def get_metadata_item(self, key: str) -> Optional[FormMetadataItem]:
        """Get a specific metadata item not tied to form fields"""
        return self.form_metadata.get(key)
    
    def get_field_schema_dict(self, page: Optional[int] = None) -> Dict[str, str]:
        """
        Get a dictionary mapping field names to their schema string representations
        """
        result = {}
        if page:
            if not self.fields_by_page.get(page):
                raise ValueError(f"Unexpected page number {page} encountered! Allowable options: {self.fields_by_page.keys()}")
            for field_name, metadata in self.fields_by_page[page].items():
                result[field_name] = metadata.to_schema_string()
        else:
            for fields_by_page in self.fields_by_page.values():
                for field_name, metadata in fields_by_page.items():
                    result[field_name] = metadata.to_schema_string()
        
        return result
