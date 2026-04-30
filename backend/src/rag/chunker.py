"""Semantic chunking utilities for resume data."""

from typing import Any, Dict, List

class ResumeChunker:
    """Chunks structured resume data into semantic segments."""

    def create_semantic_chunks(self, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Splits extracted resume JSON into coordinate-anchored semantic chunks."""
        chunks = []
        
        source_file = record.get("source_file")
        if not source_file:
            source_file = record.get("metadata", {}).get("source_file", "unknown")
    
        department = record.get("metadata", {}).get("department", "unknown")
        extracted = record.get("extracted", {})
        personal_info = extracted.get("personal_info", {})
        
        def _build_chunk(text: str, chunk_type: str) -> Dict[str, Any]:
            return {
                "text": text,
                "metadata": {
                    "source_file": source_file,
                    "department": department,
                    "chunk_type": chunk_type
                }
            }

        # Retrieve fields, falling back to personal_info if LLM nested them improperly
        summary = extracted.get("summary", "") or personal_info.get("summary", "")
        
        skills_raw = extracted.get("skills", []) or personal_info.get("skills", [])
        skills = ", ".join(skills_raw) if isinstance(skills_raw, list) else str(skills_raw)
        
        if summary or skills:
            profile_text = f"SOURCE: {source_file}\nIDENTITY: Candidate Profile ({source_file})\nSUMMARY: {summary}\nSKILLS: {skills}"
            chunks.append(_build_chunk(profile_text, "profile"))
            
        # 2. Experience Chunks
        experience_list = extracted.get("experience_list") or personal_info.get("experience_list", [])
        for exp in experience_list:
            job_title = exp.get("title", exp.get("job_title", ""))
            company = exp.get("company", "")
            dates = exp.get("dates", exp.get("duration", ""))
            description = exp.get("description", "")
            
            exp_text = f"SOURCE: {source_file}\nJOB TITLE: {job_title}\nCOMPANY: {company}\nDATES: {dates}\nDESCRIPTION: {description}"
            chunks.append(_build_chunk(exp_text, "experience"))
            
        # 3. Education Chunks
        education_list = extracted.get("education_list") or personal_info.get("education_list", [])
        for edu in education_list:
            degree = edu.get("degree", "")
            institution = edu.get("institution", edu.get("university", edu.get("school", "")))
            dates = edu.get("dates", edu.get("duration", edu.get("year", "")))
            
            edu_text = f"SOURCE: {source_file}\nDEGREE: {degree}\nINSTITUTION: {institution}\nDATES: {dates}"
            chunks.append(_build_chunk(edu_text, "education"))
            
        # 4. Projects Chunks
        projects_list = extracted.get("projects_list") or personal_info.get("projects_list", [])
        for proj in projects_list:
            name = proj.get("name", proj.get("title", ""))
            description = proj.get("description", "")
            tech = proj.get("technologies", [])
            technologies = ", ".join(tech) if isinstance(tech, list) else str(tech)
            
            proj_text = f"SOURCE: {source_file}\nPROJECT NAME: {name}\nDESCRIPTION: {description}\nTECHNOLOGIES: {technologies}"
            chunks.append(_build_chunk(proj_text, "project"))
            
        return chunks
