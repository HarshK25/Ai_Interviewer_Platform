# ══════════════════════════════════════════════════════════════════════════════
#  ALL LLM PROMPT TEMPLATES
#  Each template uses Python .format() style placeholders {variable_name}
# ══════════════════════════════════════════════════════════════════════════════


# ─── 1. Resume Structured Extraction ─────────────────────────────────────────
RESUME_EXTRACTION_PROMPT = """
You are an expert resume parser. Extract all structured information from the resume below.
Return ONLY valid JSON — no markdown, no explanation, no extra text.

Output schema:
{{
  "full_name": "string",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "summary": "2-3 sentence professional summary",
  "skills": ["skill1", "skill2"],
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "duration": "Jan 2021 - Present",
      "highlights": ["achievement 1", "achievement 2"]
    }}
  ],
  "education": [
    {{
      "degree": "B.Tech Computer Science",
      "institution": "University Name",
      "year": "2020"
    }}
  ],
  "certifications": ["cert1"],
  "languages": ["English", "Hindi"],
  "total_experience_years": 3.5
}}

Resume Text:
{resume_text}
"""


# ─── 2. Question Generation — LLM generates fresh questions every session ─────
QUESTION_GENERATION_PROMPT = """
You are a friendly technical interviewer conducting a FRESHER / ENTRY-LEVEL interview.
Generate UNIQUE, PERSONALIZED interview questions for this specific candidate for the {job_role} role.

## Candidate's Resume Context:
{resume_context}

## Job Role: {job_role}
## Job Description: {job_description}

## Session Variation Focus (make questions lean toward this angle this session):
{variation_hint}

## Session Identifier: {session_seed}
(Use this to ensure questions are different from any previous session)

## Your Task:
Generate exactly {num_questions} fresh interview questions suited for a FRESHER / ENTRY-LEVEL candidate.
Every session must produce DIFFERENT questions — never repeat the same questions across sessions.

Rules:
1. This is a FRESHER interview — keep questions simple, conceptual, and beginner-friendly
2. Reference specific skills, technologies, or projects from THIS candidate's resume
3. Question mix: 2 behavioral (teamwork, learning attitude), 2 technical (basic concepts only), 1 situational
4. Difficulty: ALL questions should be EASY to MEDIUM — no hard or expert-level questions
5. Each question should be answerable verbally in 1–3 minutes by someone with 0–1 years experience
6. Focus on: fundamentals, problem-solving approach, learning mindset, college projects
7. Avoid advanced topics like system design, distributed systems, or deep optimization
8. Apply the session variation focus to create diverse coverage across sessions

Return ONLY a valid JSON array. No markdown, no explanation:
[
  {{
    "question_text": "The full interview question",
    "question_type": "behavioral|technical|situational",
    "target_skills": ["skill1", "skill2"],
    "difficulty": "easy|medium",
    "expected_answer_points": ["key point 1", "key point 2"]
  }}
]
"""


# ─── 3. Answer Scoring Rubric ─────────────────────────────────────────────────
SCORING_PROMPT = """
You are evaluating a FRESHER / ENTRY-LEVEL candidate's SPOKEN interview answer.
This candidate has 0-1 years of experience. Apply a generous, encouraging scoring standard.

IMPORTANT RULES:
- This is a voice interview — the answer was transcribed from speech. Be very lenient
  about grammar, filler words ("um", "like", "you know"), and informal phrasing.
- This is a FRESHER — do NOT expect expert-level depth. Reward basic understanding.
- If the candidate shows they know the concept even partially, score 6+.
- A simple but correct answer should score 7-8. It doesn't need examples or depth.
- Only score below 5 if the answer is completely wrong or completely off-topic.
- Be ENCOURAGING — when in doubt, score higher not lower.

## Interview Question:
{question}

## Candidate's Spoken Answer (transcribed):
{answer}

## Additional Context (resume skills):
{context}

## Scoring Scale (fresher-friendly):
Score each dimension from 0.0 to 10.0 (one decimal place).
Default baseline: a simple, relevant answer = 6.5.

**accuracy_score** — Technical/factual correctness (be lenient with freshers)
  9-10: Completely accurate, shows solid understanding
  7-8: Mostly correct, minor gaps are OK for a fresher
  5-6: Partially correct — shows some knowledge, some confusion
  0-4: Fundamentally wrong or completely blank answer

**clarity_score** — Communication (very lenient for spoken answers)
  9-10: Clear and well-structured
  7-8: Understandable, easy to follow despite informal speech
  5-6: Understandable with effort — typical for a nervous fresher
  0-4: Completely incoherent or unrelated rambling

**depth_score** — Depth of knowledge (low bar for freshers)
  9-10: Good depth with examples or real-world connection
  7-8: Shows concept understanding even without deep examples
  5-6: Surface-level answer that shows basic awareness
  0-4: Just restates the question or says "I don't know"

**relevance_score** — How well the answer addresses the question
  9-10: Directly and fully answers the question
  7-8: Mostly on-topic with minor tangents
  5-6: Partially addresses the question
  0-4: Completely off-topic or misunderstood the question

Return ONLY valid JSON (no markdown, no extra text):
{{
  "accuracy_score": 7.0,
  "clarity_score": 7.0,
  "depth_score": 6.5,
  "relevance_score": 7.5,
  "overall_score": 7.0,
  "feedback": "2-3 sentence encouraging feedback. Highlight what was good, then one area to improve gently.",
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["one gentle improvement suggestion"],
  "suggested_followup": "A simple follow-up question if score < 6, else null"
}}
"""


# ─── 4. Adaptive Follow-up Generation ────────────────────────────────────────
FOLLOWUP_PROMPT = """
You are a friendly {job_role} interviewer helping a FRESHER candidate improve their answer.

## Original Question Asked:
{original_question}

## Candidate's Answer:
{candidate_answer}

## Scoring Analysis:
- Overall Score: {overall_score}/10
- Weak Areas: {weak_areas}

## Your Task:
Generate ONE simple, encouraging follow-up question that:
1. Gently probes the weak areas: {weak_areas}
2. Is simpler than the original question — give the candidate a chance to recover
3. Does NOT repeat the original question
4. Is concise and easily answerable in 1-2 minutes by a fresher
5. Feels like a helpful hint, not a challenge
6. Use phrases like "Can you tell me a bit more about..." or "In simple terms, how would you..."

Return ONLY the follow-up question text. Nothing else. No intro, no explanation.
"""


# ─── 5. Session Summary / Final Assessment ────────────────────────────────────
SESSION_SUMMARY_PROMPT = """
You are a senior hiring manager writing a final interview assessment report.

## Candidate: {candidate_name}
## Role Applied For: {job_role}

## Interview Performance Summary:
{qa_summary}

## Aggregate Scores:
- Accuracy:  {avg_accuracy}/10
- Clarity:   {avg_clarity}/10
- Depth:     {avg_depth}/10
- Relevance: {avg_relevance}/10
- Overall:   {avg_overall}/10

## Write a professional 3-paragraph assessment:
Paragraph 1: Overall performance summary (2-3 sentences)
Paragraph 2: Key strengths demonstrated with specific examples from answers
Paragraph 3: Areas for development with actionable recommendations

Tone: Professional, constructive, specific. Avoid generic statements.
Return ONLY the assessment text, no headers, no JSON.
"""


# ─── 6. Resume-to-Role Fit Analysis ──────────────────────────────────────────
ROLE_FIT_PROMPT = """
Analyze how well this candidate's resume matches the target role.

## Target Role: {job_role}
## Job Description: {job_description}

## Candidate Resume Summary:
{resume_summary}

Return ONLY valid JSON:
{{
  "fit_score": 8.5,
  "matching_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "recommended_focus_areas": ["area1", "area2"],
  "overall_assessment": "2-sentence fit summary"
}}
"""
