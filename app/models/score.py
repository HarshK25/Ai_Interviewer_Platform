import uuid
from sqlalchemy import Column, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Score(Base):
    __tablename__ = "scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id = Column(UUID(as_uuid=True), ForeignKey("answers.id", ondelete="CASCADE"), nullable=False, unique=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)

    # Dimension scores (0.0 - 10.0)
    accuracy_score = Column(Float)
    clarity_score = Column(Float)
    depth_score = Column(Float)
    relevance_score = Column(Float)
    overall_score = Column(Float)

    # LLM output
    llm_feedback = Column(Text)
    strengths = Column(JSONB)       # ["clear explanation", ...]
    improvements = Column(JSONB)    # ["add examples", ...]
    raw_llm_json = Column(JSONB)    # full raw LLM response
    scored_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    answer = relationship("Answer", back_populates="score")
    session = relationship("InterviewSession", back_populates="scores")

    def __repr__(self):
        return f"<Score overall={self.overall_score} for answer {self.answer_id}>"


class Scorecard(Base):
    __tablename__ = "scorecards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False, unique=True)

    # Aggregated metrics
    avg_accuracy = Column(Float)
    avg_clarity = Column(Float)
    avg_depth = Column(Float)
    avg_relevance = Column(Float)
    overall_score = Column(Float)

    # Summary
    strengths = Column(JSONB)           # top 3 strengths
    improvements = Column(JSONB)        # top 3 improvement areas
    session_summary = Column(Text)      # LLM-generated narrative
    recommendation = Column(String(50)) # strong_hire|hire|borderline|no_hire

    # Delivery
    pdf_s3_key = Column(String(500))
    email_sent = Column(String(5), default="false")
    email_sent_at = Column(DateTime(timezone=True))
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("InterviewSession", back_populates="scorecard")

    def __repr__(self):
        return f"<Scorecard session={self.session_id} [{self.recommendation}]>"
