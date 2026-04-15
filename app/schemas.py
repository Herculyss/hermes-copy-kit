from pydantic import BaseModel, Field


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
