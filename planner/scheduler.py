from datetime import datetime, timedelta
import math
from memory.database import (
    get_exam_info_db, get_topics_db, get_all_tasks_db,
    save_tasks_db, update_topic_priority_db, save_memory_db
)

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date() + timedelta(days=20)

def generate_initial_schedule(exam_info=None, topics=None):
    if not exam_info:
        exam_info = get_exam_info_db()
    if not topics:
        topics = get_topics_db()
        
    if not exam_info or not topics:
        return []
        
    exam_date = parse_date(exam_info["exam_date"])
    start_date = datetime.now().date()
    daily_capacity = float(exam_info.get("daily_hours", 3.0))
    
    total_days = max(1, (exam_date - start_date).days)
        
    # Order topics by prerequisite dependency + priority weight
    priority_weights = {"VERY HIGH": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    
    # Sort topics considering priority and estimated hours
    sorted_topics = sorted(
        topics,
        key=lambda t: (-priority_weights.get(t.get("priority", "MEDIUM"), 2), -t.get("est_hours", 3.0))
    )
    
    tasks = []
    current_day_offset = 0
    current_day_hours_used = 0.0
    
    topic_subtopics_map = {}
    for t in topics:
        subs = t.get("subtopics", [])
        if isinstance(subs, list):
            topic_subtopics_map[t["name"]] = ", ".join(subs)
        else:
            topic_subtopics_map[t["name"]] = str(subs)

    # Phase 1: Schedule Study Sessions for each topic across days
    for topic in sorted_topics:
        t_name = topic["name"]
        rem_hours = float(topic.get("est_hours", 3.0))
        t_subs = topic_subtopics_map.get(t_name, "")
        
        while rem_hours > 0 and current_day_offset < total_days:
            avail_today = daily_capacity - current_day_hours_used
            if avail_today <= 0.2: # Move to next day if less than 12 mins left
                current_day_offset += 1
                current_day_hours_used = 0.0
                continue
                
            session_duration = round(min(rem_hours, avail_today, 3.0), 1)
            d_str = (start_date + timedelta(days=current_day_offset)).strftime("%Y-%m-%d")
            
            tasks.append({
                "date": d_str,
                "topic_name": t_name,
                "task_type": "Study",
                "duration_hours": session_duration,
                "subtopics": t_subs,
                "completed": 0,
                "order_index": len(tasks)
            })
            
            current_day_hours_used += session_duration
            rem_hours -= session_duration
            
    # Phase 2: Interleave Revision and Practice Sessions
    revision_start_offset = max(1, total_days // 2)
    high_priority_topics = [t for t in sorted_topics if t.get("priority") in ["HIGH", "VERY HIGH"]]
    
    rev_day_offset = revision_start_offset
    for t in high_priority_topics:
        t_subs = topic_subtopics_map.get(t["name"], "")
        if rev_day_offset < total_days:
            d_str = (start_date + timedelta(days=rev_day_offset)).strftime("%Y-%m-%d")
            tasks.append({
                "date": d_str,
                "topic_name": t["name"],
                "task_type": "Revision",
                "duration_hours": 1.0,
                "subtopics": t_subs,
                "completed": 0,
                "order_index": len(tasks)
            })
            tasks.append({
                "date": d_str,
                "topic_name": t["name"],
                "task_type": "Practice",
                "duration_hours": 0.5,
                "subtopics": t_subs,
                "completed": 0,
                "order_index": len(tasks)
            })
            rev_day_offset += 2
            
    # Save generated tasks to DB
    save_tasks_db(tasks)
    save_memory_db("last_replanned_reason", "Initial plan generated automatically based on exam date and topic priorities.")
    return tasks

def replan_schedule(reason: str, weak_topic: str = None, new_daily_hours: float = None):
    """
    Adaptive Replanner tool.
    Recalibrates upcoming schedule based on performance or availability changes.
    """
    exam_info = get_exam_info_db()
    if not exam_info:
        return {"status": "error", "message": "No active exam setup."}
        
    if new_daily_hours:
        exam_info["daily_hours"] = float(new_daily_hours)
        
    topics = get_topics_db()
    current_tasks = get_all_tasks_db()
    
    if weak_topic:
        update_topic_priority_db(weak_topic, "VERY HIGH")
        topics = get_topics_db()
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Retain tasks marked completed
    completed_tasks = [t for t in current_tasks if t["completed"] == 1]
    
    # Calculate completed hours per date
    date_completed_hours = {}
    for t in completed_tasks:
        d = t["date"]
        date_completed_hours[d] = date_completed_hours.get(d, 0.0) + float(t["duration_hours"])
    
    # Calculate completed hours per topic
    topic_completed_hours = {}
    for t in completed_tasks:
        name = t["topic_name"]
        topic_completed_hours[name] = topic_completed_hours.get(name, 0.0) + float(t["duration_hours"])
        
    topic_subtopics_map = {}
    for t in topics:
        subs = t.get("subtopics", [])
        if isinstance(subs, list):
            topic_subtopics_map[t["name"]] = ", ".join(subs)
        else:
            topic_subtopics_map[t["name"]] = str(subs)

    start_date = datetime.now().date()
    exam_date = parse_date(exam_info["exam_date"])
    daily_capacity = float(exam_info.get("daily_hours", 3.0))
    total_days = max(1, (exam_date - start_date).days)
    
    new_future_tasks = []
    
    current_day_offset = 0
    current_day_hours_used = 0.0

    # If a weak topic was provided, schedule urgent revision session
    if weak_topic:
        w_subs = topic_subtopics_map.get(weak_topic, "")
        # Find next date with room
        while current_day_offset < total_days:
            d_str = (start_date + timedelta(days=current_day_offset)).strftime("%Y-%m-%d")
            already_done = date_completed_hours.get(d_str, 0.0) + current_day_hours_used
            if (daily_capacity - already_done) >= 1.5:
                new_future_tasks.append({
                    "date": d_str,
                    "topic_name": weak_topic,
                    "task_type": "Revision",
                    "duration_hours": 1.0,
                    "subtopics": w_subs,
                    "completed": 0,
                    "order_index": len(new_future_tasks)
                })
                new_future_tasks.append({
                    "date": d_str,
                    "topic_name": weak_topic,
                    "task_type": "Practice",
                    "duration_hours": 0.5,
                    "subtopics": w_subs,
                    "completed": 0,
                    "order_index": len(new_future_tasks)
                })
                current_day_hours_used += 1.5
                break
            current_day_offset += 1
            current_day_hours_used = 0.0

    # Sort topics by priority
    priority_weights = {"VERY HIGH": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    sorted_topics = sorted(topics, key=lambda t: -priority_weights.get(t.get("priority", "MEDIUM"), 2))
    
    for topic in sorted_topics:
        t_name = topic["name"]
        t_subs = topic_subtopics_map.get(t_name, "")
        total_est = float(topic.get("est_hours", 3.0))
        done = topic_completed_hours.get(t_name, 0.0)
        rem = max(0.0, total_est - done)
        
        if t_name == weak_topic:
            rem += 1.5
            
        while rem > 0 and current_day_offset < total_days:
            d_str = (start_date + timedelta(days=current_day_offset)).strftime("%Y-%m-%d")
            already_done = date_completed_hours.get(d_str, 0.0)
            avail = daily_capacity - already_done - current_day_hours_used
            
            if avail <= 0.2:
                current_day_offset += 1
                current_day_hours_used = 0.0
                continue
                
            block = round(min(rem, avail, 3.0), 1)
            new_future_tasks.append({
                "date": d_str,
                "topic_name": t_name,
                "task_type": "Study",
                "duration_hours": block,
                "subtopics": t_subs,
                "completed": 0,
                "order_index": len(new_future_tasks)
            })
            current_day_hours_used += block
            rem -= block

    all_updated = completed_tasks + new_future_tasks
    save_tasks_db(all_updated)
    
    explanation = f"Schedule adapted: {reason}. "
    if weak_topic:
        explanation += f"Prioritized urgent revision and extra study time for weak topic '{weak_topic}'."
    if new_daily_hours:
        explanation += f" Adjusted daily capacity to {new_daily_hours} hours/day."
        
    save_memory_db("last_replanned_reason", explanation)
    
    return {
        "status": "success",
        "explanation": explanation,
        "total_tasks": len(all_updated)
    }
