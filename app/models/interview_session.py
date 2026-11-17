import uuid
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id = Column(UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True)
    job_role = Column(String(255), nullable=False)
    job_description = Column(Text)
    status = Column(String(50), default="pending")   # pending|active|completed|aborted
    total_questions = Column(Integer, default=5)
    current_question_index = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="sessions")
    resume = relationship("Resume", back_populates="sessions")
    questions = relationship("Question", back_populates="session", cascade="all, delete-orphan", order_by="Question.sequence_num")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="session", cascade="all, delete-orphan")
    scorecard = relationship("Scorecard", back_populates="session", uselist=False)

    def __repr__(self):
        return f"<Session {self.id} [{self.status}] for {self.job_role}>"
