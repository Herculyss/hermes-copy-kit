from pydantic import BaseModel, Field
from typing import Optional


class GenerateCopyRequest(BaseModel):
    product_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1)


class GenerateCopyResponse(BaseModel):
    product_name: str
    variations: list[str]


class ScriptSections(BaseModel):
    hook: str = Field(..., min_length=1)
    problem: str = Field(..., min_length=1)
    solution: str = Field(..., min_length=1)
    cta: str = Field(..., min_length=1)


class GenerateScriptRequest(BaseModel):
    product_name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    style: str = Field(..., min_length=1)


class GenerateScriptResponse(BaseModel):
    product_name: str
    style: str
    duration_seconds: int
    script: ScriptSections


class VerifyLicenseRequest(BaseModel):
    license_key: str = Field(..., min_length=1)


class VerifyLicenseResponse(BaseModel):
    valid: bool


class GenerateLicenseRequest(BaseModel):
    email: str = Field(..., min_length=3)
    source: str = Field(default="gumroad", min_length=1)
    order_id: str = Field(..., min_length=1)


class GenerateLicenseResponse(BaseModel):
    license_key: str


class RetrieveLicenseRequest(BaseModel):
    email: str = Field(..., min_length=3)
    order_id: Optional[str] = None


class RetrieveLicenseResponse(BaseModel):
    found: bool
    license_key: Optional[str] = None
