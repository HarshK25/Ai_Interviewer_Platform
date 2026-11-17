from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from app.database import get_db, AsyncSessionLocal
from app.models.interview_session import InterviewSession
from app.models.question import Question
from app.models.answer import Answer
from app.services.voice_engine import voice_engine
from app.services.scoring_engine import scoring_engine
from app.services.question_generator import question_generator
from app.utils.file_storage import storage
import json
import uuid
import logging

router = APIRouter(prefix="/voice", tags=["Voice & Interview Loop"])
logger = logging.getLogger(__name__)


# ─── WebSocket Interview Loop ─────────────────────────────────────────────────
@router.websocket("/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """
    Real-time voice interview WebSocket.

    Protocol (JSON messages):
    ← CLIENT sends:  {type: "audio", data: <base64-encoded-webm-audio>}
    → SERVER sends:  {type: "question", text, audio_url, num, total}
                     {type: "score", data: {scores, feedback}}
                     {type: "followup", text, audio_url}
                     {type: "complete"}
                     {type: "error", message}
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    try:
        async with AsyncSessionLocal() as db:
            # Load session + questions
            result = await db.execute(
                select(InterviewSession)
                .where(InterviewSession.id == session_id)
                .options(selectinload(InterviewSession.questions))
            )
            session = result.scalar_one_or_none()

            if not session:
                await websocket.send_json({"type": "error", "message": "Session not found"})
                await websocket.close()
                return

            if session.status != "active":
                await websocket.send_json({"type": "error", "message": f"Session is {session.status}"})
                await websocket.close()
                return

            questions = sorted(session.questions, key=lambda q: q.sequence_num)

            for i, question in enumerate(questions):
                # 1️⃣ Send question to client
                audio_url = await storage.get_presigned_url(question.audio_s3_key)
                await websocket.send_json({
                    "type": "question",
                    "num": i + 1,
                    "total": len(questions),
                    "text": question.question_text,
                    "audio_url": audio_url,
                    "question_type": question.question_type,
                    "difficulty": question.difficulty,
                })

                # 2️⃣ Receive audio answer from client
                audio_bytes = await websocket.receive_bytes()

                # 3️⃣ Save audio to MinIO
                audio_key = f"audio/answers/{session_id}/q{i+1}_{uuid.uuid4()}.webm"
                await storage.upload(audio_bytes, audio_key, "audio/webm")

                # 4️⃣ Transcribe with Whisper
                transcript_result = await voice_engine.transcribe_audio(audio_bytes, f"q{i+1}.webm")
                transcript_text = transcript_result["text"]

                # 5️⃣ Save answer to DB
                answer = Answer(
                    question_id=question.id,
                    session_id=session.id,
                    audio_s3_key=audio_key,
                    transcript=transcript_text,
                    duration_secs=transcript_result.get("duration", 0),
                    word_count=len(transcript_text.split()),
                    whisper_language=transcript_result.get("language", "en"),
                )
                db.add(answer)
                await db.flush()

                # 6️⃣ Score with LLM
                score_data = await scoring_engine.score_answer(
                    question=question.question_text,
                    answer=transcript_text,
                    job_role=session.job_role,
                )
                await scoring_engine.save_score(db, str(answer.id), str(session.id), score_data)

                # 7️⃣ Send score to client
                await websocket.send_json({
                    "type": "score",
                    "question_num": i + 1,
                    "transcript": transcript_text,
                    "data": score_data,
                })

                # 8️⃣ Adaptive follow-up if score < 6
                if score_data.get("overall_score", 10) < 6.0:
                    followup_text = await question_generator.generate_followup(
                        original_question=question.question_text,
                        candidate_answer=transcript_text,
                        score_data=score_data,
                        job_role=session.job_role,
                    )
                    followup_audio_key = await voice_engine.synthesize_speech(
                        followup_text, session_id, f"{i+1}_followup"
                    )
                    followup_audio_url = await storage.get_presigned_url(followup_audio_key)

                    # Save follow-up question
                    followup_q = Question(
                        session_id=session.id,
                        sequence_num=len(questions) + i + 1,
                        question_text=followup_text,
                        question_type="followup",
                        source="llm_generated",
                        audio_s3_key=followup_audio_key,
                        is_followup="yes",
                        parent_question_id=question.id,
                    )
                    db.add(followup_q)
                    await db.flush()

                    await websocket.send_json({
                        "type": "followup",
                        "text": followup_text,
                        "audio_url": followup_audio_url,
                    })

                    # Receive and score follow-up answer too
                    followup_audio_bytes = await websocket.receive_bytes()
                    followup_transcript = await voice_engine.transcribe_audio(followup_audio_bytes, "followup.webm")
                    followup_answer = Answer(
                        question_id=followup_q.id,
                        session_id=session.id,
                        transcript=followup_transcript["text"],
                        word_count=len(followup_transcript["text"].split()),
                    )
                    db.add(followup_answer)

                await db.commit()

            # 9️⃣ Mark session complete + trigger scorecard
            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Trigger background scorecard generation
            from app.tasks.pdf_tasks import generate_scorecard_task
            generate_scorecard_task.delay(str(session_id))

            await websocket.send_json({"type": "complete", "message": "Interview complete! Scorecard is being generated."})

    except WebSocketDisconnect:
        logger.warning(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ─── REST STT Endpoint ────────────────────────────────────────────────────────
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Standalone endpoint to transcribe audio to text using Whisper."""
    audio_bytes = await file.read()
    result = await voice_engine.transcribe_audio(audio_bytes, file.filename)
    return result


# ─── REST TTS Endpoint ────────────────────────────────────────────────────────
@router.post("/synthesize")
async def synthesize_speech_endpoint(text: str, session_id: str = "test", q_num: int = 0):
    """Standalone TTS endpoint — returns a presigned URL to the audio file."""
    key = await voice_engine.synthesize_speech(text, session_id, q_num)
    url = await storage.get_presigned_url(key)
    return {"audio_url": url, "s3_key": key}
