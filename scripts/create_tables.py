"""Create database tables if they don't already exist (safe to run multiple times)."""
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Prefer the DATABASE_URL env var (set inside Docker), fall back to local dev default
DB = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:62635494@localhost:5433/ai_interviewer"
)


async def main():
    engine = create_async_engine(DB, echo=False)

    # Check what already exists
    async with engine.connect() as conn:
        res = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        existing = [r[0] for r in res.fetchall()]
        print("Existing tables:", existing)

    # Create tables only if they don't exist — never drop, preserves all data
    CREATE = [
        'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',

        """CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email VARCHAR(255) UNIQUE NOT NULL,
            full_name VARCHAR(255) NOT NULL,
            hashed_password VARCHAR(255),
            role VARCHAR(50) DEFAULT 'candidate',
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS resumes (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            filename VARCHAR(255),
            s3_key VARCHAR(500),
            raw_text TEXT,
            parsed_data JSONB,
            chroma_doc_ids JSONB,
            uploaded_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS interview_sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            resume_id UUID REFERENCES resumes(id),
            job_role VARCHAR(255) NOT NULL,
            job_description TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            total_questions INTEGER DEFAULT 5,
            current_question_index INTEGER DEFAULT 0,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS questions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            sequence_num INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            question_type VARCHAR(50),
            source VARCHAR(50),
            difficulty VARCHAR(20),
            target_skills JSONB,
            context_chunks JSONB,
            audio_s3_key VARCHAR(500),
            is_followup VARCHAR(10) DEFAULT 'no',
            parent_question_id UUID REFERENCES questions(id),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS answers (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            question_id UUID UNIQUE NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            session_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            audio_s3_key VARCHAR(500),
            transcript TEXT,
            duration_secs FLOAT,
            word_count INTEGER,
            whisper_language VARCHAR(10),
            submitted_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS scores (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            answer_id UUID UNIQUE NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
            session_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
            accuracy_score FLOAT,
            clarity_score FLOAT,
            depth_score FLOAT,
            relevance_score FLOAT,
            overall_score FLOAT,
            llm_feedback TEXT,
            strengths JSONB,
            improvements JSONB,
            raw_llm_json JSONB,
            scored_at TIMESTAMPTZ DEFAULT NOW()
        )""",

        """CREATE TABLE IF NOT EXISTS scorecards (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID UNIQUE NOT NULL REFERENCES interview_sessions(id),
            avg_accuracy FLOAT,
            avg_clarity FLOAT,
            avg_depth FLOAT,
            avg_relevance FLOAT,
            overall_score FLOAT,
            strengths JSONB,
            improvements JSONB,
            session_summary TEXT,
            recommendation VARCHAR(50),
            pdf_s3_key VARCHAR(500),
            email_sent VARCHAR(5) DEFAULT 'false',
            email_sent_at TIMESTAMPTZ,
            generated_at TIMESTAMPTZ DEFAULT NOW()
        )""",
    ]

    async with engine.begin() as conn:
        print("\nCreating tables (IF NOT EXISTS — data is preserved)...")
        for stmt in CREATE:
            await conn.execute(text(stmt))
            name = [w for w in stmt.split() if w.isupper() and len(w) > 2]
            print(f"  OK: {' '.join(name[:4])}")

    await engine.dispose()
    print("\nAll tables ready!")


if __name__ == "__main__":
    asyncio.run(main())
