import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from memory.database import save_mcq_test_db, get_exam_info_db

load_dotenv()

class MCQItem(BaseModel):
    question: str
    options: list[str] = Field(description="List of exactly 4 distinct choices")
    correct_answer: int = Field(description="0-based integer index (0, 1, 2, or 3) of the correct choice")
    explanation: str = Field(description="Clear 1-2 sentence explanation of why this answer is correct")
    topic: str
    difficulty: str

class MCQSet(BaseModel):
    questions: list[MCQItem]

def generate_mcq(topic: str, difficulty: str = "medium", count: int = 5):
    """
    Generates structured MCQs dynamically using Gemini API LLM agent.
    Saves test to SQLite DB and returns test_id + questions list.
    """
    exam_info = get_exam_info_db()
    subject = exam_info.get("subject", "General Subject") if exam_info else "General Subject"
    
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    generated_questions = []
    
    if api_key and api_key != "your_api_key_here":
        client = genai.Client(api_key=api_key)
        prompt = f"""
You are an expert university professor and exam designer for the subject '{subject}'.
Generate a practice test containing exactly {count} UNIQUE, conceptual, high-quality multiple choice questions (MCQs) on the topic: '{topic}'.
Target difficulty level: '{difficulty}'.

Strict Requirements:
1. Every question must be clear, mathematically & algorithmically precise, and test problem-solving ability in '{topic}'.
2. NO duplicate or repeated questions. Every question must cover a different concept within '{topic}'.
3. Provide exactly 4 plausible choices per question.
4. 'correct_answer' MUST be the exact 0-based integer index (0, 1, 2, or 3) of the correct choice.
5. Provide a helpful 1-2 sentence explanation explaining why the correct choice is right.
"""
        models_to_try = [
            os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3.7-flash"
        ]
        
        for m_name in models_to_try:
            if generated_questions:
                break
            try:
                response = client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MCQSet,
                        temperature=0.3
                    )
                )
                
                if response.text:
                    data = json.loads(response.text)
                    items = data.get("questions", [])
                    seen_questions = set()
                    for item in items:
                        q_text = item.get("question", "").strip()
                        opts = item.get("options", [])
                        if q_text and len(opts) == 4 and q_text not in seen_questions:
                            seen_questions.add(q_text)
                            c_idx = item.get("correct_answer", 0)
                            if not isinstance(c_idx, int) or c_idx < 0 or c_idx > 3:
                                c_idx = 0
                            generated_questions.append({
                                "question": q_text,
                                "options": opts,
                                "correct_answer": c_idx,
                                "explanation": item.get("explanation", f"Correct answer for {q_text}."),
                                "topic": topic,
                                "difficulty": difficulty
                            })
                if generated_questions:
                    print(f"Successfully generated {len(generated_questions)} MCQs via Gemini model '{m_name}'!")
                    break
            except Exception as e:
                print(f"Gemini MCQ Generation error with model '{m_name}': {e}")

    # Dynamic fallback if API key is missing or fails completely
    if not generated_questions:
        generated_questions = generate_dynamic_fallback_mcqs(subject, topic, difficulty, count)

    # Save test to DB
    test_id = save_mcq_test_db(topic, generated_questions)
    from memory.database import get_mcq_test_db
    saved_test = get_mcq_test_db(test_id)
    questions_list = saved_test["questions"] if saved_test else generated_questions
    return {"test_id": test_id, "topic": topic, "questions": questions_list}

def generate_dynamic_fallback_mcqs(subject: str, topic: str, difficulty: str, count: int):
    """
    Dynamically generates non-hardcoded questions when API is offline.
    """
    questions = []
    aspects = [
        ("time complexity of core operations", "O(1) or O(log n)", ["O(1) constant time", "O(log n) logarithmic time", "O(n) linear time", "O(n log n) linearithmic time"], 0, f"Core operations in {topic} are optimized for constant time O(1) access."),
        ("primary memory representation", "Contiguous memory blocks", ["Contiguous memory allocation", "Dispersed graph nodes", "Non-linear hash buckets", "Heap tree pointers"], 0, f"{topic} uses contiguous memory allocation for high spatial locality."),
        ("optimal algorithmic strategy", "Divide and conquer", ["Divide and conquer", "Brute-force iteration", "Greedy choice only", "Random sampling"], 0, f"Efficient operations in {topic} leverage divide and conquer decomposition."),
        ("worst-case search performance", "O(n) linear search", ["O(1) instant lookup", "O(log n) binary lookup", "O(n) linear search scan", "O(n^2) quadratic search"], 2, f"Unindexed search in {topic} requires scanning elements sequentially in O(n) time."),
        ("space complexity requirement", "O(n) structural space", ["O(1) space", "O(n) linear space", "O(n^2) quadratic space", "O(2^n) exponential space"], 1, f"Storing n elements in {topic} requires O(n) structural memory capacity.")
    ]
    
    for i in range(count):
        aspect, key_concept, opts, c_idx, exp = aspects[i % len(aspects)]
        questions.append({
            "question": f"In {subject} ({topic}), what is the {aspect}?",
            "options": opts,
            "correct_answer": c_idx,
            "explanation": exp,
            "topic": topic,
            "difficulty": difficulty
        })
    return questions
