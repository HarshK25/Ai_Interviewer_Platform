import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """
    Manages 3 ChromaDB collections:
      - resume_chunks      : chunked resume text per candidate
      - question_bank      : curated role-specific questions
      - answer_history     : past answers for analytics
    """

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._init_collections()
        logger.info(f"ChromaDB initialized at {settings.CHROMA_PERSIST_DIR}")

    def _init_collections(self):
        self.resume_collection = self.client.get_or_create_collection(
            name="resume_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        self.question_bank_collection = self.client.get_or_create_collection(
            name="question_bank",
            metadata={"hnsw:space": "cosine"},
        )
        self.answer_history_collection = self.client.get_or_create_collection(
            name="answer_history",
            metadata={"hnsw:space": "cosine"},
        )

    # ─── Resume Operations ────────────────────────────────────────────────────

    def add_resume_chunks(self, chunks: list[dict], user_id: str, resume_id: str) -> list[str]:
        """
        Add resume text chunks to the vector store.
        chunks: [{"text": "...", "chunk_type": "skills|experience|education|general"}]
        Returns: list of document IDs added
        """
        doc_ids = [f"{resume_id}_chunk_{i}" for i in range(len(chunks))]
        self.resume_collection.add(
            documents=[c["text"] for c in chunks],
            metadatas=[
                {
                    "user_id": user_id,
                    "resume_id": resume_id,
                    "chunk_type": c.get("chunk_type", "general"),
                }
                for c in chunks
            ],
            ids=doc_ids,
        )
        logger.info(f"Added {len(chunks)} resume chunks for user {user_id}")
        return doc_ids

    def query_resume(self, query: str, user_id: str, n_results: int = 5) -> dict:
        """Semantic search over a specific user's resume chunks."""
        return self.resume_collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"user_id": user_id},
        )

    def delete_resume_chunks(self, resume_id: str):
        """Delete all chunks for a specific resume."""
        results = self.resume_collection.get(where={"resume_id": resume_id})
        if results["ids"]:
            self.resume_collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for resume {resume_id}")

    # ─── Question Bank Operations ─────────────────────────────────────────────

    def add_question_bank_items(self, questions: list[dict]):
        """
        Seed the question bank with role-specific questions.
        questions: [{text, role, difficulty, category, question_type}]
        """
        doc_ids = [f"qbank_{q['role']}_{i}" for i, q in enumerate(questions)]
        self.question_bank_collection.add(
            documents=[q["text"] for q in questions],
            metadatas=[
                {
                    "role": q["role"],
                    "difficulty": q.get("difficulty", "medium"),
                    "category": q.get("category", "general"),
                    "question_type": q.get("question_type", "behavioral"),
                }
                for q in questions
            ],
            ids=doc_ids,
        )
        logger.info(f"Added {len(questions)} question bank items")

    def query_question_bank(self, role: str, topic: str, n_results: int = 10) -> dict:
        """Retrieve relevant questions from the bank for a given role and topic."""
        return self.question_bank_collection.query(
            query_texts=[topic],
            n_results=n_results,
            where={"role": role},
        )

    # ─── Answer History Operations ────────────────────────────────────────────

    def add_answer(self, answer_text: str, session_id: str, question_id: str):
        self.answer_history_collection.add(
            documents=[answer_text],
            metadatas=[{"session_id": session_id, "question_id": question_id}],
            ids=[f"ans_{question_id}"],
        )

    def get_collection_counts(self) -> dict:
        return {
            "resume_chunks": self.resume_collection.count(),
            "question_bank": self.question_bank_collection.count(),
            "answer_history": self.answer_history_collection.count(),
        }


# Singleton
chroma_client = ChromaDBClient()
