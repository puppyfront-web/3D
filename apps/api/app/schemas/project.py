"""Project schemas."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.schemas.common import APIBaseModel
from pydantic import Field

from app.schemas.company import CompanyOut
from app.schemas.user import UserOut


class ProjectBase(APIBaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=50)
    screen_info: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None


class ProjectCreate(ProjectBase):
    company_id: uuid.UUID
    owner_id: uuid.UUID
    status: str = Field(default="draft", max_length=50)


class ProjectUpdate(APIBaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    company_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(None, max_length=50)
    priority: Optional[str] = Field(None, max_length=50)
    screen_info: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None


class ProjectOut(ProjectBase):
    id: uuid.UUID
    company_id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    company: Optional[CompanyOut] = None
    owner: Optional[UserOut] = None


class ProjectStatusUpdate(APIBaseModel):
    status: str = Field(..., max_length=50, description="New status value")


# ─── Wizard create (mirrors the frontend's nested ProjectWizardData) ──────────
# APIBaseModel applies alias_generator=to_camel + populate_by_name=True,
# so snake_case fields below accept the frontend's camelCase payload as-is.


class ScreenInfoSchema(APIBaseModel):
    """Venue & screen parameters — domain-critical inputs for 3D-wall generation."""

    screen_type: Optional[str] = None
    screen_size: Optional[str] = None
    pitch: Optional[str] = None
    resolution: Optional[str] = None
    install_environment: Optional[str] = None
    viewing_distance: Optional[str] = None
    main_viewpoint: Optional[str] = None
    notes: Optional[str] = None


class WizardStep1(APIBaseModel):
    project_name: str = Field(..., max_length=255)
    client_name: str = Field(..., max_length=255)
    industry: Optional[str] = None
    project_type: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=50)
    due_date: Optional[str] = None


class WizardStep2(APIBaseModel):
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    competitors: Optional[str] = None
    target_market: Optional[str] = None
    existing_materials: Optional[bool] = None
    material_links: Optional[str] = None


class WizardStep3(APIBaseModel):
    proposal_style: Optional[str] = None
    language: Optional[str] = None
    tone_of_voice: Optional[str] = None
    key_selling_points: Optional[str] = None
    required_sections: Optional[List[str]] = None
    additional_requirements: Optional[str] = None


class WizardStep4(APIBaseModel):
    visual_style: Optional[str] = None
    color_scheme: Optional[str] = None
    image_style: Optional[str] = None
    brand_guidelines: Optional[str] = None
    number_of_images: Optional[int] = None
    resolutions: Optional[List[str]] = None


class WizardStep5(APIBaseModel):
    quality_level: Optional[str] = None
    review_criteria: Optional[List[str]] = None
    auto_export: Optional[bool] = None
    export_formats: Optional[List[str]] = None
    notify_email: Optional[str] = None


class ProjectWizardCreate(APIBaseModel):
    """Nested wizard payload submitted by the frontend create-project flow.

    The service resolves owner (default seeded user) and create-or-gets the
    Company from step1/step2, so the frontend never has to supply
    company_id/owner_id directly.
    """

    step1: WizardStep1
    step2: Optional[WizardStep2] = None
    step3: Optional[WizardStep3] = None
    step4: Optional[WizardStep4] = None
    step5: Optional[WizardStep5] = None
    screen: Optional[ScreenInfoSchema] = None
