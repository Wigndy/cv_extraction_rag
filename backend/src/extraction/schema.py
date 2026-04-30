"""Pydantic schema definitions for structured resume outputs."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class ResumeSchema(BaseModel):
    personal_info: Dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="")
    experience_list: List[Dict[str, Any]] = Field(default_factory=list)
    education_list: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
