"""Prompt templates used for deterministic resume extraction."""

SYSTEM_PROMPT = """
You are an expert resume parser.
Extract information from the provided resume text and return only fields that
belong to the schema.

Rules:
1. Do not hallucinate missing facts.
2. If data is unavailable, return empty strings or empty arrays.
3. Keep all detected skills as concise tokens.
4. Normalize role and company names without adding new information.
5. Preserve chronology where possible.
""".strip()


def build_user_prompt(resume_text: str) -> str:
	"""Build the user prompt payload for structured extraction.

	Args:
		resume_text: Raw text extracted from a resume.

	Returns:
		Prompt string embedding the resume text.
	"""
	return (
		"Extract structured resume data from the following content:\n\n"
		f"{resume_text}\n\n"
		"Return data using the provided schema only."
	)
