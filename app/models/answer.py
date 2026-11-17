import uuid
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    audio_s3_key = Column(String(500))          # raw recorded audio
    transcript = Column(Text)                   # Whisper STT output
    duration_secs = Column(Float)               # audio duration
    word_count = Column(Integer)                # derived from transcript
    whisper_language = Column(String(10))       # detected language
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    question = relationship("Question", back_populates="answer")
    session = relationship("InterviewSession", back_populates="answers")
    score = relationship("Score", back_populates="answer", uselist=False)

    def __repr__(self):
        return f"<Answer for Q:{self.question_id} [{self.word_count} words]>"
