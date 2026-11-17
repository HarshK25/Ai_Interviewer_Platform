import io
import json
import re
import logging
import pymupdf as fitz                   # PyMuPDF (use pymupdf import to suppress deprecation warning)
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.llm.llm_client import llm
from app.llm.prompt_templates import RESUME_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class ResumeParser:

    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " "],
        )

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Extract raw text from PDF or DOCX file."""
        fname = filename.lower()
        if fname.endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text.strip()
        elif fname.endswith(".docx"):
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        raise ValueError(f"Unsupported file type: {filename}. Use PDF or DOCX.")

    async def parse_structured(self, raw_text: str) -> dict:
        """Use LLM to extract structured JSON from resume text."""
        prompt = RESUME_EXTRACTION_PROMPT.format(resume_text=raw_text[:8000])
        try:
            response = await llm.ainvoke(prompt)
            content = response.content
            # Strip markdown code fences if present
            content = re.sub(r"```json\s*|\s*```", "", content).strip()
            return json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM resume parse failed: {e}. Using fallback.")
            return {
                "full_name": "Unknown",
                "email": None,
                "skills": [],
                "experience": [],
                "education": [],
                "summary": raw_text[:300],
            }

    def chunk_resume(self, raw_text: str, parsed_data: dict = None) -> list[dict]:
        """
        Split resume into semantically meaningful chunks with type labels.
        Returns: [{"text": "...", "chunk_type": "skills|experience|education|general"}]
        """
        chunks = []

        # If we have structured data, create dedicated chunks per section
        if parsed_data:
            if parsed_data.get("skills"):
                skills_text = "Skills: " + ", ".join(parsed_data["skills"])
                chunks.append({"text": skills_text, "chunk_type": "skills"})

            for exp in parsed_data.get("experience", []):
                exp_text = f"{exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')}): " + \
                           " ".join(exp.get("highlights", []))
                if exp_text.strip():
                    chunks.append({"text": exp_text, "chunk_type": "experience"})

            for edu in parsed_data.get("education", []):
                edu_text = f"{edu.get('degree', '')} from {edu.get('institution', '')} ({edu.get('year', '')})"
                chunks.append({"text": edu_text, "chunk_type": "education"})

        # Also chunk raw text for semantic coverage
        raw_chunks = self.text_splitter.split_text(raw_text)
        for chunk in raw_chunks:
            chunks.append({"text": chunk, "chunk_type": "general"})

        return chunks


resume_parser = ResumeParser()
