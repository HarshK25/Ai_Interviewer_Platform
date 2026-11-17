"""Initial schema — all 6 tables + pgvector extension

Revision ID: 001
Revises: 
Create Date: 2026-11-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255)),
        sa.Column('role', sa.String(50), server_default='candidate'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # ── resumes ──────────────────────────────────────────────────────────────
    op.create_table(
        'resumes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255)),
        sa.Column('s3_key', sa.String(500)),
        sa.Column('raw_text', sa.Text()),
        sa.Column('parsed_data', postgresql.JSONB()),
        sa.Column('chroma_doc_ids', postgresql.JSONB()),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # ── interview_sessions ───────────────────────────────────────────────────
    op.create_table(
        'interview_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('resume_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('resumes.id'), nullable=False),
        sa.Column('job_role', sa.String(255), nullable=False),
        sa.Column('job_description', sa.Text()),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('total_questions', sa.Integer(), server_default='5'),
        sa.Column('current_question_index', sa.Integer(), server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    op.create_index('ix_sessions_user_id', 'interview_sessions', ['user_id'])
    op.create_index('ix_sessions_status', 'interview_sessions', ['status'])

    # ── questions ────────────────────────────────────────────────────────────
    op.create_table(
        'questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence_num', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(50)),
        sa.Column('source', sa.String(50)),
        sa.Column('difficulty', sa.String(20)),
        sa.Column('target_skills', postgresql.JSONB()),
        sa.Column('context_chunks', postgresql.JSONB()),
        sa.Column('audio_s3_key', sa.String(500)),
        sa.Column('is_followup', sa.String(10), server_default='no'),
        sa.Column('parent_question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('questions.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # ── answers ──────────────────────────────────────────────────────────────
    op.create_table(
        'answers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('audio_s3_key', sa.String(500)),
        sa.Column('transcript', sa.Text()),
        sa.Column('duration_secs', sa.Float()),
        sa.Column('word_count', sa.Integer()),
        sa.Column('whisper_language', sa.String(10)),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # ── scores ───────────────────────────────────────────────────────────────
    op.create_table(
        'scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('answer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('answers.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('accuracy_score', sa.Float()),
        sa.Column('clarity_score', sa.Float()),
        sa.Column('depth_score', sa.Float()),
        sa.Column('relevance_score', sa.Float()),
        sa.Column('overall_score', sa.Float()),
        sa.Column('llm_feedback', sa.Text()),
        sa.Column('strengths', postgresql.JSONB()),
        sa.Column('improvements', postgresql.JSONB()),
        sa.Column('raw_llm_json', postgresql.JSONB()),
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # ── scorecards ───────────────────────────────────────────────────────────
    op.create_table(
        'scorecards',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('interview_sessions.id'), nullable=False, unique=True),
        sa.Column('avg_accuracy', sa.Float()),
        sa.Column('avg_clarity', sa.Float()),
        sa.Column('avg_depth', sa.Float()),
        sa.Column('avg_relevance', sa.Float()),
        sa.Column('overall_score', sa.Float()),
        sa.Column('strengths', postgresql.JSONB()),
        sa.Column('improvements', postgresql.JSONB()),
        sa.Column('session_summary', sa.Text()),
        sa.Column('recommendation', sa.String(50)),
        sa.Column('pdf_s3_key', sa.String(500)),
        sa.Column('email_sent', sa.String(5), server_default='false'),
        sa.Column('email_sent_at', sa.DateTime(timezone=True)),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # ── answer_embeddings (pgvector) ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE answer_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            answer_id UUID REFERENCES answers(id) ON DELETE CASCADE,
            embedding vector(768),
            model_used VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX ON answer_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table('answer_embeddings')
    op.drop_table('scorecards')
    op.drop_table('scores')
    op.drop_table('answers')
    op.drop_table('questions')
    op.drop_table('interview_sessions')
    op.drop_table('resumes')
    op.drop_table('users')
