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
You are a senior technical interviewer. Your job is to generate UNIQUE, PERSONALIZED
interview questions for this specific candidate for the {job_role} role.

## Candidate's Resume Context:
{resume_context}

## Job Role: {job_role}
## Job Description: {job_description}

## Session Variation Focus (make questions lean toward this angle this session):
{variation_hint}

## Session Identifier: {session_seed}
(Use this to ensure questions are different from any previous session)

## Your Task:
Generate exactly {num_questions} fresh interview questions. Every session must produce
DIFFERENT questions — never repeat the same questions across sessions.

Rules:
1. Reference SPECIFIC skills, technologies, projects, or experiences from THIS candidate's resume
2. Question mix: 2 behavioral, 2 technical, 1 situational
3. Progressive difficulty: start medium → end hard
4. Each question should be answerable verbally in 2–4 minutes
5. Do NOT use generic questions — tailor every question to this specific resume
6. Apply the session variation focus to create diverse coverage across sessions

Return ONLY a valid JSON array. No markdown, no explanation:
[
  {{
    "question_text": "The full interview question",
    "question_type": "behavioral|technical|situational",
    "target_skills": ["skill1", "skill2"],
    "difficulty": "easy|medium|hard",
    "expected_answer_points": ["key point 1", "key point 2"]
  }}
]
"""


# ─── 3. Answer Scoring Rubric ─────────────────────────────────────────────────
SCORING_PROMPT = """
You are an expert {job_role} interviewer evaluating a candidate's SPOKEN interview answer.

IMPORTANT: This is a voice interview — the answer was transcribed from speech. Be lenient
about grammar, filler words, and informal phrasing. Focus on the substance and knowledge shown.

## Interview Question:
{question}

## Candidate's Spoken Answer (transcribed):
{answer}

## Additional Context (resume skills):
{context}

## Scoring Instructions:
Score each dimension from 0.0 to 10.0 (one decimal place).
Average answers should score 5-6. Good answers 7-8. Excellent answers 9-10.

**accuracy_score** — Technical/factual correctness
  9-10: Completely accurate, demonstrates mastery
  7-8: Mostly correct with minor gaps
  5-6: Partially correct, some errors
  0-4: Significant factual errors or misconceptions

**clarity_score** — Communication & structure (lenient for spoken answers)
  9-10: Exceptionally clear and well-structured
  7-8: Well-organized and easy to follow
  5-6: Understandable despite informal phrasing
  0-4: Very confusing or incoherent

**depth_score** — Depth of knowledge & examples
  9-10: Expert-level depth, discusses trade-offs
  7-8: Good depth with concrete examples
  5-6: Surface-level but shows understanding
  0-4: Very superficial or just restates the question

**relevance_score** — How well the answer addresses the question
  9-10: Fully addresses all parts of the question
  7-8: Mostly relevant with minor tangents
  5-6: Partially addresses the question
  0-4: Mostly off-topic or misunderstood the question

Return ONLY valid JSON (no markdown, no extra text):
{{
  "accuracy_score": 6.5,
  "clarity_score": 7.0,
  "depth_score": 5.5,
  "relevance_score": 7.5,
  "overall_score": 6.6,
  "feedback": "2-3 sentence constructive feedback focusing on what was good and what to improve",
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["improvement area 1"],
  "suggested_followup": "A specific follow-up question if score < 6, else null"
}}
"""


# ─── 4. Adaptive Follow-up Generation ────────────────────────────────────────
FOLLOWUP_PROMPT = """
You are a skilled {job_role} interviewer conducting a follow-up probe.

## Original Question Asked:
{original_question}

## Candidate's Answer:
{candidate_answer}

## Scoring Analysis:
- Overall Score: {overall_score}/10
- Weak Areas: {weak_areas}

## Your Task:
Generate ONE targeted follow-up question that:
1. Specifically probes the weak areas: {weak_areas}
2. Does NOT repeat the original question
3. Pushes the candidate to demonstrate deeper knowledge
4. Is concise and answerable in 1-3 minutes verbally
5. Feels natural in the flow of conversation

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
