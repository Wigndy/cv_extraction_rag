import os
import json
from pathlib import Path
from typing import Any

import yaml
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from langchain_ollama import ChatOllama
from pydantic import ValidationError
from tenacity import Retrying, stop_after_attempt, wait_fixed

from src.extraction.schema import ResumeSchema

# SYSTEM_PROMPT = """You are an expert Resume AI Extractor. Your task is to extract highly structured JSON data from resume content.
# You will receive up to two versions of the resume text:
# - DIGITAL_TEXT: The raw text layer extracted directly from the PDF.
# - VISUAL_TEXT: The OCR output from scanning the visual layout.

# Rules for Extraction:
# 1. CROSS-REFERENCE: If both texts are provided, use them to validate each other. Use the DIGITAL_TEXT for precise characters and the VISUAL_TEXT to understand layout or recover dropped text.
# 2. ELIMINATE ARTIFACTS: Clean up garbage characters like 'â€', 'ï¼', random symbols, or malformed bullet points.
# 3. IGNORE HEADERS/FOOTERS: Do not include page numbers, dates of print, or repetitive headers in the content.
# 4. DO NOT HALLUCINATE: If information is missing, use empty strings or empty lists.
# 5. JSON ONLY: Return strictly valid JSON conforming to the schema.
# """
SYSTEM_PROMPT = """Extract resume data to concise JSON. 
Rules:
1. SOURCE: Select and use ONLY the clearest version between DIGITAL_TEXT and VISUAL_TEXT.
2. CLEAN: Remove artifacts (â€, ï¼), headers, and footers.
3. BREVITY: Summarize experiences and projects very briefly.
4. JSON ONLY: No hallucination. Return strictly valid JSON.
"""

# def build_user_prompt(digital_text: str | None, visual_text: str | None) -> str:
#     prompt = "Extract the resume data based on the following content:\n\n"
#     if digital_text:
#         prompt += f"--- DIGITAL_TEXT ---\n{digital_text}\n\n"
#     if visual_text:
#         prompt += f"--- VISUAL_TEXT ---\n{visual_text}\n\n"
#     return prompt
def build_user_prompt(digital_text: str | None, visual_text: str | None) -> str:
    prompt = "Resume Content:\n"
    if digital_text:
        prompt += f"--- DIGITAL ---\n{digital_text}\n"
    if visual_text:
        prompt += f"--- OCR ---\n{visual_text}\n"
    return prompt

def _load_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)

class ResumeExtractor:
    def __init__(self):
        config = _load_config()
        extraction = config.get("extraction", {})
        self.max_retries = int(extraction.get("max_retries", 3))
        self.retry_wait_seconds = int(extraction.get("retry_wait_seconds", 2))
        self.ollama_base_url = os.getenv(extraction.get("base_url_env", "OLLAMA_BASE_URL"), "http://localhost:11434")
        self.model_name = extraction.get("model_name", "qwen2.5:7b")
        self.temperature = float(extraction.get("temperature", 0.0))
        
        self.parser = PydanticOutputParser(pydantic_object=ResumeSchema)
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.ollama_base_url,
            temperature=self.temperature,
            format="json",
        )
        self.fixing_parser = OutputFixingParser.from_llm(parser=self.parser, llm=self.llm)

    def extract(self, digital_text: str | None, visual_text: str | None) -> ResumeSchema:
        prompt = build_user_prompt(digital_text, visual_text)
        full_prompt = f"{prompt}\n\nReturn only valid JSON.\n{self.parser.get_format_instructions()}"

        retrying = Retrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_fixed(self.retry_wait_seconds),
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                response = self.llm.invoke(
                    [
                        ("system", SYSTEM_PROMPT),
                        ("human", full_prompt),
                    ]
                )
                raw = response.content if hasattr(response, "content") else str(response)

                try:
                    if isinstance(raw, list):
                        raw = "".join([str(part) for part in raw])
                    return ResumeSchema.model_validate_json(raw)
                except (ValidationError, json.JSONDecodeError, TypeError):
                    fixed = self.fixing_parser.parse(raw)
                    if isinstance(fixed, ResumeSchema):
                        return fixed
                    if isinstance(fixed, dict):
                        return ResumeSchema.model_validate(fixed)
                    if isinstance(fixed, str):
                        return ResumeSchema.model_validate_json(fixed)
                    raise ValueError("Could not parse model output into ResumeSchema")

        raise RuntimeError("Extraction failed after retries")
