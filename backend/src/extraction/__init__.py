"""Extraction package for schema-driven resume entity extraction."""

from src.extraction.processor import ResumeExtractor
from src.extraction.schema import ResumeSchema

__all__ = ["ResumeExtractor", "ResumeSchema"]
