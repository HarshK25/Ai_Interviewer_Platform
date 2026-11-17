import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_num = Column(Integer, nullable=False)              # 1-based order
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50))                          # behavioral|technical|situational|followup
    source = Column(String(50))                                 # rag_generated|question_bank|llm_generated
    difficulty = Column(String(20))                             # easy|medium|hard
    target_skills = Column(JSONB)                               # ["Python", "REST APIs"]
    context_chunks = Column(JSONB)                              # resume chunks that inspired question
    audio_s3_key = Column(String(500))                          # TTS audio file in MinIO/S3
    is_followup = Column(String(50), default="no")              # no|yes
    parent_question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("InterviewSession", back_populates="questions")
    answer = relationship("Answer", back_populates="question", uselist=False)
    followups = relationship("Question", backref="parent_question", remote_side=[id])

    def __repr__(self):
        return f"<Question #{self.sequence_num} [{self.question_type}]>"
