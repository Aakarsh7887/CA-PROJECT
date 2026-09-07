import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from memory.database import (
    init_db, save_exam_info, get_exam_info_db,
    save_topics_db, get_topics_db, get_all_tasks_db,
    set_task_completed_db, get_test_history_db, get_memory_db,
    save_memory_db, reset_all_data
)
from planner.planner import analyze_syllabus_with_gemini
from planner.scheduler import generate_initial_schedule, replan_schedule
from testing.mcq_generator import generate_mcq
from testing.evaluator import evaluate_test, analyze_performance
from agent.agent import run_agent_loop

load_dotenv()

app = Flask(__name__)
CORS(app)

# Ensure DB is initialized on startup
with app.app_context():
    init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/setup", methods=["POST"])
def api_setup():
    data = request.json or {}
    exam_date = data.get("exam_date")
    subject = data.get("subject")
    syllabus = data.get("syllabus")
    daily_hours = float(data.get("daily_hours", 3.0))
    
    if not exam_date or not subject or not syllabus:
        return jsonify({"status": "error", "message": "Exam date, subject, and syllabus are required."}), 400
        
    # 1. Save exam info
    save_exam_info(exam_date, subject, daily_hours)
    exam_info = get_exam_info_db()
    
    # 2. Analyze syllabus with Gemini
    topics = analyze_syllabus_with_gemini(subject, syllabus)
    save_topics_db(topics)
    
    # 3. Generate initial day-by-day study schedule using explicit exam_info and topics
    schedule = generate_initial_schedule(exam_info=exam_info, topics=topics)
    
    return jsonify({
        "status": "success",
        "exam_info": exam_info,
        "topics_count": len(topics),
        "tasks_count": len(schedule)
    })

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    try:
        exam_info = get_exam_info_db()
        if not exam_info:
            return jsonify({"has_setup": False})
            
        try:
            e_date = datetime.strptime(exam_info["exam_date"], "%Y-%m-%d").date()
            days_remaining = (e_date - datetime.now().date()).days
        except Exception:
            days_remaining = 0
            
        all_tasks = get_all_tasks_db()
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if t.get("completed") == 1)
        overall_progress = round((completed_tasks / total_tasks * 100.0), 1) if total_tasks > 0 else 0.0
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_tasks = [t for t in all_tasks if t.get("date") == today_str and t.get("completed") == 0]
        if not today_tasks and all_tasks:
            uncompleted = [t for t in all_tasks if t.get("completed") == 0]
            if uncompleted:
                target_d = uncompleted[0].get("date")
                today_tasks = [t for t in all_tasks if t.get("date") == target_d and t.get("completed") == 0]
                
        topics = get_topics_db()
        weak_topics = [t for t in topics if t.get("priority") in ["HIGH", "VERY HIGH"] or float(t.get("proficiency", 0.0)) < 50.0]
        
        recent_tests = get_test_history_db()[:5]
        ai_recommendation = get_memory_db("ai_recommendation", "Plan created! Start your study sessions and take tests to get personalized recommendations.")
        last_replan_reason = get_memory_db("last_replanned_reason", "")
        
        return jsonify({
            "has_setup": True,
            "exam_info": exam_info,
            "days_remaining": days_remaining,
            "overall_progress": overall_progress,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "today_plan": today_tasks,
            "all_schedule": all_tasks,
            "weak_topics": weak_topics,
            "all_topics": topics,
            "recent_tests": recent_tests,
            "ai_recommendation": ai_recommendation,
            "last_replan_reason": last_replan_reason
        })
    except Exception as err:
        print(f"API Dashboard Error: {err}")
        import traceback
        traceback.print_exc()
        return jsonify({"has_setup": False, "error": str(err)}), 500

@app.route("/api/tasks/<int:task_id>/complete", methods=["POST"])
def api_complete_task(task_id):
    data = request.json or {}
    completed = data.get("completed", 1)
    set_task_completed_db(task_id, completed)
    # Trigger Adaptive Replanner to recalculate remaining future tasks
    replan_schedule(reason=f"Task #{task_id} marked as {'completed' if completed else 'pending'}.")
    return jsonify({"status": "success", "task_id": task_id, "completed": completed})

@app.route("/api/mcq/generate", methods=["POST"])
def api_generate_mcq():
    data = request.json or {}
    topic = data.get("topic", "General")
    difficulty = data.get("difficulty", "medium")
    count = int(data.get("count", 5))
    
    result = generate_mcq(topic, difficulty, count)
    return jsonify(result)

@app.route("/api/mcq/submit", methods=["POST"])
def api_submit_mcq():
    data = request.json or {}
    test_id = int(data.get("test_id"))
    user_answers = data.get("user_answers", {})
    
    res = evaluate_test(test_id, user_answers)
    return jsonify(res)

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.json or {}
    message = data.get("message", "")
    if not message.strip():
        return jsonify({"status": "error", "message": "Message is required."}), 400
        
    agent_output = run_agent_loop(message)
    return jsonify({
        "status": "success",
        "response": agent_output["response"],
        "tool_calls": agent_output["tool_calls"]
    })

@app.route("/api/settings/hours", methods=["POST"])
def api_update_hours():
    data = request.json or {}
    hours = float(data.get("daily_hours", 3.0))
    res = replan_schedule(f"User changed daily study hours to {hours}h.", new_daily_hours=hours)
    return jsonify(res)

@app.route("/api/reset", methods=["POST"])
def api_reset():
    reset_all_data()
    return jsonify({"status": "success", "message": "All data reset successfully."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
