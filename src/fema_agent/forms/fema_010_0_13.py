from fema_agent.forms.form import Form, FormFieldMetadata, FormMetadataItem

def create_fema_form_010_0_13() -> Form:
    """
    Create a Form object for FEMA Form 010-0-13 (Request for Presidential Disaster Declaration)
    """
    form = Form(
        name="Request for Presidential Disaster Declaration",
        form_number="010-0-13"
    )
    
    # Add form metadata
    form.form_metadata["form_version_date"] = FormMetadataItem(
        description="Form version date shown in bottom left corner",
        location="bottom left corner",
        page=1,
        format="(M/YY)"
    )
    form.form_metadata["omb_control_number"] = FormMetadataItem(
        description="OMB Control Number shown in top right corner",
        location="top right corner",
        page=1,
        format="####-####"
    )
    form.form_metadata["expiration_date"] = FormMetadataItem(
        description="Form expiration date shown in top right corner",
        location="top right corner",
        page=1,
        format="MM/DD/YYYY"
    )
    
    # Page 1 fields
    form.fields_by_page[1] = {
        "request_date": FormFieldMetadata(
            description="Request Date",
            field_number="1"
        ),
        "state_or_tribe": FormFieldMetadata(
            description="Name of State (as defined in Stafford Act 103, 42 U.S.C. § 5122) or Indian tribal government requesting declaration",
            field_number="2a"
        ),
        "population": FormFieldMetadata(
            description="Population (as reported by 2010 Census) or estimated population of Indian tribal government's damaged area(s)",
            field_number="2b"
        ),
        "governor_name": FormFieldMetadata(
            description="Governor's or Tribal Chief Executive's Name",
            field_number="3"
        ),
        "coordinator_designation": FormFieldMetadata(
            description="Designation of State or Tribal Coordinating Officer upon declaration (if available) and phone number",
            field_number="4"
        ),
        "representative_designation": FormFieldMetadata(
            description="Designation of Governor's Authorized Representative or Tribal Chief Executive Representative upon declaration (if available) and phone number",
            field_number="5"
        ),
        "request_purpose": FormFieldMetadata(
            description="Declaration Request For",
            field_number="6",
            options=["Major Disaster (Stafford Act Sec. 401)", "Emergency (Stafford Act Sec. 501(a))"]
        ),
        "incident_period_beginning_date": FormFieldMetadata(
            description="Incident Period: Beginning Date",
            field_number="7"
        ),
        "incident_period_end_date": FormFieldMetadata(
            description="Incident Period: End Date",
            field_number="7"
        ),
        "incident_period_continuing": FormFieldMetadata(
            description="Incident Period: Continuing",
            field_number="7",
            is_boolean=True
        ),
        "incident_type": FormFieldMetadata(
            description="Type of Incident (Check all that apply)",
            field_number="7b",
            is_multi_select=True,
            options=[
                "Drought", "Earthquake", "Explosion", "Fire", "Flood", "Hurricane", "Landslide",
                "Mudslide", "Severe Storm", "Snowstorm", "Straight-Line Winds", "Tidal Wave", 
                "Tornado", "Tropical Depression", "Tropical Storm", "Tsunami", "Volcanic Eruption",
                "Winter Storm", "Other"
            ]
        ),
        "incident_type_other_details": FormFieldMetadata(
            description="Other (please specify)",
            field_number="7b"
        ),
        "damage_description": FormFieldMetadata(
            description="Description of damages (Short description of impacts of disaster on affected area and population). Include additional details in enclosed Governor's or Tribal Chief Executive's cover letter.",
            field_number="8"
        ),
        "resource_description": FormFieldMetadata(
            description="Description of the nature and amount of State and local or Indian tribal government resources which have been or will be committed. Include additional details in enclosed Governor's or Tribal Chief Executive's cover letter.",
            field_number="9"
        )
    }
    
    # Page 2 fields
    form.fields_by_page[2] = {
        "ia_requested": FormFieldMetadata(
            description="Individual Assistance",
            field_number="10",
            is_boolean=True
        ),
        "ia_request_date": FormFieldMetadata(
            description="Individual Assistance Dates Performed: Requested",
            field_number="10"
        ),
        "ia_start_date": FormFieldMetadata(
            description="Individual Assistance Dates Performed: Start",
            field_number="10"
        ),
        "ia_end_date": FormFieldMetadata(
            description="Individual Assistance Dates Performed: End",
            field_number="10"
        ),
        "ia_accessibility_problems": FormFieldMetadata(
            description="Individual Assistance Accessibility Problems (Areas that could not be accessed, and why)",
            field_number="10"
        ),
        "pa_requested": FormFieldMetadata(
            description="Public Assistance",
            field_number="10",
            is_boolean=True
        ),
        "pa_request_date": FormFieldMetadata(
            description="Public Assistance Dates Performed: Requested",
            field_number="10"
        ),
        "pa_start_date": FormFieldMetadata(
            description="Public Assistance Dates Performed: Start",
            field_number="10"
        ),
        "pa_end_date": FormFieldMetadata(
            description="Public Assistance Dates Performed: End",
            field_number="10"
        ),
        "pa_accessibility_problems": FormFieldMetadata(
            description="Public Assistance Accessibility Problems (Areas that could not be accessed, and why)",
            field_number="10"
        ),
        "ia_requested_programs": FormFieldMetadata(
            description="Individual Assistance Programs",
            field_number="11",
            is_multi_select=True,
            options=[
                "N/A", 
                "Individuals and Households Program", 
                "Crisis Counseling Program",
                "Disaster Unemployment Assistance", 
                "Disaster Case Management", 
                "Disaster Legal Services",
                "Small Business Administration (SBA) Disaster Assistance",
                "All"
            ]
        ),
        "ia_programs_needed_per_area": FormFieldMetadata(
            description="For the following jurisdictions, specify programs and areas (counties, parishes, independent cities; for Indian tribal government, list tribe(s) and/or tribal area(s)) If additional space is needed, please enclose additional documentation).",
            field_number="11"
        ),
        "ia_affected_tribes": FormFieldMetadata(
            description="For States, identify Federally-recognized Tribes in the requested counties (if applicable).",
            field_number="11"
        )
    }
    
    # Page 3 fields
    form.fields_by_page[3] = {
        "pa_categories_requested": FormFieldMetadata(
            description="Public Assistance Categories",
            field_number="11",
            is_multi_select=True,
            options=[
                "N/A", 
                "Debris Removal (Category A)", 
                "Emergency Protective Measures (Category B)",
                "Permanent Work (Categories C-G)"
            ]
        ),
        "pa_programs_needed_per_area": FormFieldMetadata(
            description="For the following jurisdictions, specify programs and areas (counties, parishes, independent cities; for Indian tribal government, list tribe(s) and/or tribal area(s)). If additional space is needed or your request includes different categories of work for different jurisdictions; please enclose additional documentation.",
            field_number="11"
        ),
        "pa_affected_tribes": FormFieldMetadata(
            description="For States, identify Federally-recognized Tribes included in the requested counties (if applicable).",
            field_number="11"
        ),
        "debris_removal_needed": FormFieldMetadata(
            description="I anticipate the need for debris removal, which poses an immediate threat to lives, public health and safety.",
            field_number="Indemnification for Debris Removal Activity",
            is_boolean=True
        ),
        "direct_federal_assistance_requested": FormFieldMetadata(
            description="""
            One of two checkboxes. If the following box is checked, return False: "I do not request direct Federal assistance at this time." If the other box is checked, return True: "I request direct Federal assistance for work and services to save lives and protect property."
            """,
            field_number="Request for Direct Federal Assistance",
            is_boolean=True
        ),
        "direct_federal_assistance_types": FormFieldMetadata(
            description="I request the following type(s) of assistance:",
            field_number="a"
        ),
        "direct_federal_assistance_reasons": FormFieldMetadata(
            description="List of reasons why State and local or Indian tribal government cannot perform, or contract for, required work and services.",
            field_number="b"
        ),
        "snow_assistance_requested": FormFieldMetadata(
            description="I request snow assistance.",
            field_number="Request for Snow Assistance",
            is_boolean=True
        ),
        "snow_assistance_jurisdictions": FormFieldMetadata(
            description="Snow assistance for the following jurisdictions (Specify counties, independent cities or tribes and/or tribal areas).",
            field_number="Request for Snow Assistance"
        )
    }
    
    # Page 4 fields
    form.fields_by_page[4] = {
        "hazard_mitigation_statewide": FormFieldMetadata(
            description="Hazard Mitigation: Statewide",
            field_number="11",
            is_boolean=True
        ),
        "hazard_mitigation_specific_areas": FormFieldMetadata(
            description="For the following specific counties, parishes, independent cities or tribes and/or tribal areas.",
            field_number="11"
        ),
        "mitigation_plan_expiration_date": FormFieldMetadata(
            description="Mitigation Plan Expiration Date",
            field_number="12a"
        ),
        "mitigation_plan_type": FormFieldMetadata(
            description="Type of Plan",
            field_number="12b",
            options=["Enhanced", "Standard"]
        ),
        "other_agency_requirements_anticipated": FormFieldMetadata(
            description="I do anticipate requirements from Other Federal Agencies",
            field_number="13",
            is_boolean=True
        ),
        "certification_completed": FormFieldMetadata(
            description="I certify the following",
            field_number="14",
            is_boolean=True
        ),
        "emergency_plan_execution_date": FormFieldMetadata(
            description="In response to this incident, I have taken appropriate action under State or tribal law and have directed the execution of the State or Tribal Emergency Plan on",
            field_number="14b"
        ),
        "supporting_documentation": FormFieldMetadata(
            description="List of Enclosures and Supporting Documentation",
            field_number="15",
            is_multi_select=True,
            options=[
                "Cover Letter", 
                "Enclosure A (Individual Assistance)", 
                "Enclosure B (Public Assistance)",
                "Enclosure C (Requirements for Other Federal Agency Programs)", 
                "Enclosure D (Historic and Current Snowfall Data)",
                "Additional Supporting Documentation"
            ]
        ),
        "additional_documentation_details": FormFieldMetadata(
            description="Additional Supporting Documentation details",
            field_number="15"
        )
    }
    
    return form

# Create a singleton instance for easy import
FEMA_FORM_010_0_13 = create_fema_form_010_0_13()
