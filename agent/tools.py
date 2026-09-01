from memory.database import (
    get_exam_info_db, get_topics_db, get_all_tasks_db,
    set_task_completed_db, set_daily_hours_db, get_test_history_db,
    update_topic_priority_db, save_memory_db, get_memory_db,
    get_mcq_test_db
)
from planner.scheduler import generate_initial_schedule, replan_schedule
from testing.mcq_generator import generate_mcq as generate_mcq_impl
from testing.evaluator import evaluate_test as evaluate_test_impl, analyze_performance as analyze_perf_impl
from datetime import datetime

def get_exam_info():
    """Returns the current exam setup info (subject, exam date, daily hours)."""
    return get_exam_info_db() or {"status": "error", "message": "No exam setup found."}

def get_topics():
    """Returns all syllabus topics with their difficulty, priority, estimated hours, and proficiency."""
    return get_topics_db()

def get_current_schedule():
    """Returns the full generated study schedule (all tasks grouped by date)."""
    return get_all_tasks_db()

def get_today_tasks():
    """Returns the study tasks scheduled for today."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    all_tasks = get_all_tasks_db()
    today_tasks = [t for t in all_tasks if t["date"] == today_str]
    if not today_tasks and all_tasks:
        # Fallback to first uncompleted tasks day
        uncompleted = [t for t in all_tasks if t["completed"] == 0]
        if uncompleted:
            target_date = uncompleted[0]["date"]
            today_tasks = [t for t in all_tasks if t["date"] == target_date]
    return today_tasks

def get_topic_progress(topic: str):
    """Returns progress, test scores, and scheduled tasks for a specific topic."""
    topics = get_topics_db()
    matched = [t for t in topics if t["name"].lower() == topic.lower()]
    all_tasks = get_all_tasks_db()
    topic_tasks = [t for t in all_tasks if t["topic_name"].lower() == topic.lower()]
    completed_hours = sum(t["duration_hours"] for t in topic_tasks if t["completed"] == 1)
    total_est = matched[0]["est_hours"] if matched else 3.0
    
    return {
        "topic": topic,
        "details": matched[0] if matched else None,
        "completed_hours": completed_hours,
        "total_est_hours": total_est,
        "completion_pct": min(100.0, round((completed_hours / total_est * 100.0), 1)) if total_est > 0 else 0,
        "tasks": topic_tasks
    }

def get_test_history():
    """Returns the history of all MCQ tests taken by the user."""
    return get_test_history_db()

def create_study_plan():
    """Creates/generates the initial day-by-day study plan based on exam info and topics."""
    tasks = generate_initial_schedule()
    return {"status": "success", "message": f"Generated {len(tasks)} tasks study schedule.", "tasks_count": len(tasks)}

def update_study_plan():
    """Triggers adaptive replanning of the study schedule based on current progress and test history."""
    res = replan_schedule(reason="Manual or automated agent trigger to recalculate study plan.")
    return res

def mark_task_complete(task_id: int):
    """Marks a specific scheduled task as completed (1)."""
    set_task_completed_db(task_id, completed=1)
    replan_schedule(reason=f"Task #{task_id} marked complete by assistant.")
    return {"status": "success", "message": f"Task {task_id} marked as completed and future schedule re-balanced."}

def change_daily_hours(hours: float):
    """Updates the daily available study hours capacity and dynamically replans the schedule."""
    set_daily_hours_db(hours)
    res = replan_schedule(reason=f"User updated daily study capacity to {hours} hours/day.", new_daily_hours=hours)
    return res

def generate_mcq(topic: str, difficulty: str = "medium", count: int = 5):
    """Generates an MCQ test on a given topic with specified difficulty and question count."""
    return generate_mcq_impl(topic=topic, difficulty=difficulty, count=count)

def evaluate_test(test_id: int, user_answers: dict = None):
    """Evaluates user answers for an MCQ test, computes score, and triggers Performance Agent analysis."""
    if user_answers is None:
        user_answers = {}
    return evaluate_test_impl(test_id, user_answers)

def analyze_performance():
    """Runs the Performance Agent to identify weak/strong topics and return actionable study recommendations."""
    history = get_test_history_db()
    if not history:
        return {"status": "info", "recommendation": "No tests taken yet. Try taking an MCQ test first!"}
    latest_test = history[0]
    return analyze_perf_impl(latest_test["id"])

def update_topic_priority(topic: str, priority: str):
    """Updates the priority (LOW, MEDIUM, HIGH, VERY HIGH) for a topic."""
    update_topic_priority_db(topic, priority)
    return {"status": "success", "message": f"Updated priority of {topic} to {priority}."}

def save_memory(key: str, value: str):
    """Saves a key-value memory entry to persistent storage."""
    save_memory_db(key, value)
    return {"status": "success", "message": f"Saved memory for '{key}'."}

# Master Tool Mapping Dictionary for execution lookup
AVAILABLE_TOOLS = {
    "get_exam_info": get_exam_info,
    "get_topics": get_topics,
    "get_current_schedule": get_current_schedule,
    "get_today_tasks": get_today_tasks,
    "get_topic_progress": get_topic_progress,
    "get_test_history": get_test_history,
    "create_study_plan": create_study_plan,
    "update_study_plan": update_study_plan,
    "mark_task_complete": mark_task_complete,
    "change_daily_hours": change_daily_hours,
    "generate_mcq": generate_mcq,
    "evaluate_test": evaluate_test,
    "analyze_performance": analyze_performance,
    "update_topic_priority": update_topic_priority,
    "save_memory": save_memory,
}
