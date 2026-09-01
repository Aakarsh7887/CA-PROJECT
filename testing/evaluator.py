import os
import json
from dotenv import load_dotenv
from google import genai
from memory.database import (
    get_mcq_test_db, update_mcq_test_results_db,
    update_topic_proficiency_db, update_topic_priority_db,
    save_memory_db, get_topics_db
)
from planner.scheduler import replan_schedule

load_dotenv()

def evaluate_test(test_id: int, user_answers: dict):
    """
    Grades user answers deterministically, updates SQLite DB, and triggers Performance Agent analysis.
    """
    result = update_mcq_test_results_db(test_id, user_answers)
    test_details = get_mcq_test_db(test_id)
    
    # Trigger Performance Agent Analysis
    analysis = analyze_performance(test_id, test_details)
    
    return {
        "score_summary": result,
        "test_details": test_details,
        "performance_analysis": analysis
    }

def analyze_performance(test_id: int = None, test_details: dict = None):
    """
    Capability 4: Performance Agent.
    Analyzes test score, updates proficiency, identifies weak/strong areas,
    generates AI recommendations, and triggers adaptive replanning if score < 50%.
    """
    if test_id and not test_details:
        test_details = get_mcq_test_db(test_id)
        
    if not test_details:
        return {"recommendation": "Complete an MCQ test to receive AI performance analysis."}
        
    topic_name = test_details["topic"]
    score_pct = float(test_details.get("score_pct", 0.0))
    correct = test_details.get("correct_count", 0)
    total = test_details.get("total_questions", 0)
    
    # Update topic proficiency in database
    update_topic_proficiency_db(topic_name, score_pct)
    
    weak_areas = []
    strong_areas = []
    
    for q in test_details.get("questions", []):
        q_text = q.get("question_text", "")
        if q.get("is_correct") == 1:
            strong_areas.append(q_text[:40] + "...")
        else:
            weak_areas.append(q_text[:40] + "...")
            
    is_weak = score_pct < 50.0
    is_strong = score_pct >= 85.0
    
    # Build AI Recommendation & Replan
    recommendation_text = ""
    replan_summary = None
    
    if is_weak:
        # Boost topic priority to VERY HIGH
        update_topic_priority_db(topic_name, "VERY HIGH")
        recommendation_text = f"Your {topic_name} performance dropped to {score_pct:.0f}%. I recommend spending 60 minutes revising {topic_name} today before moving to other topics."
        
        # Trigger Adaptive Replanner!
        replan_summary = replan_schedule(
            reason=f"Poor test score on '{topic_name}' ({correct}/{total}, {score_pct:.0f}%)",
            weak_topic=topic_name
        )
        
        save_memory_db("weak_topics_list", json.dumps([topic_name]))
        save_memory_db("ai_recommendation", recommendation_text)
        
    elif is_strong:
        update_topic_priority_db(topic_name, "LOW")
        recommendation_text = f"Great work! You scored {score_pct:.0f}% in {topic_name}. Topic proficiency is high. You can move to next priority topics."
        
        replan_summary = replan_schedule(
            reason=f"High test score on '{topic_name}' ({score_pct:.0f}%)",
            weak_topic=None
        )
        save_memory_db("ai_recommendation", recommendation_text)
    else:
        update_topic_priority_db(topic_name, "MEDIUM")
        recommendation_text = f"Solid score of {score_pct:.0f}% in {topic_name}. Standard study schedule retained."
        save_memory_db("ai_recommendation", recommendation_text)

    # Use Gemini for deeper insight if available
    api_key = os.getenv("GEMINI_API_KEY")
    gemini_insight = ""
    if api_key and api_key != "your_api_key_here":
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""
You are an AI Performance Agent analyzing student exam test performance.
Topic: {topic_name}
Score: {correct}/{total} ({score_pct}%)

Strong concepts demonstrated: {strong_areas[:2]}
Concepts needing improvement: {weak_areas[:3]}

Provide a 2-sentence empathetic, constructive feedback summary and 1 specific actionable study recommendation.
"""
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt
            )
            if response.text:
                gemini_insight = response.text.strip()
        except Exception:
            pass
            
    if gemini_insight:
        recommendation_text = gemini_insight
        save_memory_db("ai_recommendation", recommendation_text)

    analysis_result = {
        "topic": topic_name,
        "score_pct": score_pct,
        "correct": correct,
        "total": total,
        "status": "Weak Area" if is_weak else ("Mastered" if is_strong else "Moderate"),
        "weak_subtopics": weak_areas,
        "strong_subtopics": strong_areas,
        "recommendation": recommendation_text,
        "replanned": replan_summary is not None
    }
    
    return analysis_result
