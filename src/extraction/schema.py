"""Pydantic schema definitions for structured resume outputs.

These models define the canonical JSON contract for parsed resume data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
	"""Personal identity and contact information extracted from a resume."""

	full_name: str = Field(default="")
	email: str = Field(default="")
	phone: str = Field(default="")
	location: str = Field(default="")
	linkedin: str = Field(default="")
	github: str = Field(default="")


class ExperienceItem(BaseModel):
	"""Single work experience entry."""

	company: str = Field(default="")
	role: str = Field(default="")
	start_date: str = Field(default="")
	end_date: str = Field(default="")
	responsibilities: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
	"""Single education entry."""

	institution: str = Field(default="")
	degree: str = Field(default="")
	field_of_study: str = Field(default="")
	start_date: str = Field(default="")
	end_date: str = Field(default="")
	grade: str = Field(default="")


class ResumeExtraction(BaseModel):
	"""Structured representation of a parsed resume document."""

	personal_info: PersonalInfo = Field(default_factory=PersonalInfo, alias="Personal Info")
	summary: str = Field(default="", alias="Summary")
	skills: list[str] = Field(default_factory=list, alias="Skills")
	experience: list[ExperienceItem] = Field(default_factory=list, alias="Experience")
	education: list[EducationItem] = Field(default_factory=list, alias="Education")

	model_config = {
		"populate_by_name": True,
	}


class ResumeRecord(BaseModel):
	"""Envelope object combining metadata with structured extraction output."""

	text: str
	metadata: dict[str, str]
	extracted: ResumeExtraction
