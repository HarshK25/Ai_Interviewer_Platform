"""
Seed script: Load question bank JSON into ChromaDB.
Run ONCE before starting the application:
    python scripts/seed_question_bank.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from pathlib import Path
from app.vector_store.chroma_client import chroma_client

QUESTION_BANK_PATH = Path("data/question_banks/question_bank.json")


def seed():
    print("📚 Loading question bank into ChromaDB...")

    with open(QUESTION_BANK_PATH) as f:
        bank = json.load(f)

    all_questions = []
    for role, questions in bank.items():
        for q in questions:
            all_questions.append({
                "text": q["text"],
                "role": role,
                "difficulty": q.get("difficulty", "medium"),
                "category": q.get("category", "general"),
                "question_type": q.get("question_type", "behavioral"),
            })

    chroma_client.add_question_bank_items(all_questions)

    counts = chroma_client.get_collection_counts()
    print(f"✅ Seeded {len(all_questions)} questions into ChromaDB")
    print(f"   Collection counts: {counts}")


if __name__ == "__main__":
    seed()
