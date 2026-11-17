import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255))
    s3_key = Column(String(500))
    raw_text = Column(Text)
    parsed_data = Column(JSONB)          # {skills, experience, education, summary}
    chroma_doc_ids = Column(JSONB)       # list of ChromaDB document IDs
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="resumes")
    sessions = relationship("InterviewSession", back_populates="resume")

    def __repr__(self):
        return f"<Resume {self.filename} for user {self.user_id}>"
