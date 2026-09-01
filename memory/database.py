import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examprep.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Exam Info Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exam_info (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        exam_date TEXT NOT NULL,
        subject TEXT NOT NULL,
        daily_hours REAL DEFAULT 3.0,
        created_at TEXT NOT NULL
    )
    """)
    
    # 2. Topics Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        difficulty TEXT DEFAULT 'Medium',
        priority TEXT DEFAULT 'MEDIUM',
        est_hours REAL DEFAULT 3.0,
        proficiency REAL DEFAULT 0.0,
        subtopics TEXT DEFAULT '[]',
        prerequisites TEXT DEFAULT '[]',
        notes TEXT DEFAULT ''
    )
    """)
    
    # 3. Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        topic_name TEXT NOT NULL,
        task_type TEXT NOT NULL,
        duration_hours REAL NOT NULL,
        subtopics TEXT DEFAULT '',
        completed INTEGER DEFAULT 0,
        order_index INTEGER DEFAULT 0
    )
    """)
    
    # 4. MCQ Tests Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mcq_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        created_at TEXT NOT NULL,
        total_questions INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        score_pct REAL DEFAULT 0.0
    )
    """)
    
    # 5. MCQ Questions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mcq_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        user_answer INTEGER DEFAULT -1,
        explanation TEXT DEFAULT '',
        is_correct INTEGER DEFAULT 0,
        FOREIGN KEY (test_id) REFERENCES mcq_tests (id) ON DELETE CASCADE
    )
    """)
    
    # 6. Agent Memory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_memory (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    
    # Migration: Add subtopics column if database was created before schema update
    try:
        cursor.execute("ALTER TABLE topics ADD COLUMN subtopics TEXT DEFAULT '[]'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN subtopics TEXT DEFAULT ''")
    except Exception:
        pass

    conn.commit()
    conn.close()

# Helper DB Functions

def save_exam_info(exam_date, subject, daily_hours=3.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT OR REPLACE INTO exam_info (id, exam_date, subject, daily_hours, created_at)
    VALUES (1, ?, ?, ?, ?)
    """, (exam_date, subject, daily_hours, now))
    conn.commit()
    conn.close()

def get_exam_info_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exam_info WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def set_daily_hours_db(hours):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE exam_info SET daily_hours = ? WHERE id = 1", (hours,))
    conn.commit()
    conn.close()

def save_topics_db(topics_data):
    """
    topics_data is a list of dicts:
    [{name, difficulty, priority, est_hours, subtopics, prerequisites}]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    for t in topics_data:
        name = t.get("name")
        diff = t.get("difficulty", "Medium")
        prio = t.get("priority", "MEDIUM")
        est = t.get("est_hours", 3.0)
        subtopics = json.dumps(t.get("subtopics", []))
        prereqs = json.dumps(t.get("prerequisites", []))
        
        cursor.execute("""
        INSERT INTO topics (name, difficulty, priority, est_hours, proficiency, subtopics, prerequisites)
        VALUES (?, ?, ?, ?, 0.0, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            difficulty=excluded.difficulty,
            priority=excluded.priority,
            est_hours=excluded.est_hours,
            subtopics=excluded.subtopics,
            prerequisites=excluded.prerequisites
        """, (name, diff, prio, est, subtopics, prereqs))
    conn.commit()
    conn.close()

def get_topics_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM topics ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["subtopics"] = json.loads(d.get("subtopics", "[]"))
        except Exception:
            d["subtopics"] = []
        try:
            d["prerequisites"] = json.loads(d.get("prerequisites", "[]"))
        except Exception:
            d["prerequisites"] = []
        results.append(d)
    return results

def update_topic_priority_db(topic_name, priority):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE topics SET priority = ? WHERE name = ?", (priority, topic_name))
    conn.commit()
    conn.close()

def update_topic_proficiency_db(topic_name, proficiency):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE topics SET proficiency = ? WHERE name = ?", (proficiency, topic_name))
    conn.commit()
    conn.close()

def save_tasks_db(tasks_list):
    """
    tasks_list: list of dicts [{date, topic_name, task_type, duration_hours, subtopics, completed, order_index}]
    Replaces all schedule tasks cleanly.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete existing tasks to prevent duplication when re-inserting updated schedule
    cursor.execute("DELETE FROM tasks")
    for t in tasks_list:
        sub_str = t.get("subtopics", "")
        if isinstance(sub_str, list):
            sub_str = ", ".join(sub_str)
            
        cursor.execute("""
        INSERT INTO tasks (date, topic_name, task_type, duration_hours, subtopics, completed, order_index)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (t["date"], t["topic_name"], t["task_type"], t["duration_hours"], sub_str, t.get("completed", 0), t.get("order_index", 0)))
        
    # Extra safety: remove any duplicate rows by date, topic_name, task_type, duration_hours, and completed state
    cursor.execute("""
    DELETE FROM tasks 
    WHERE id NOT IN (
        SELECT MIN(id) 
        FROM tasks 
        GROUP BY date, topic_name, task_type, duration_hours, completed
    )
    """)
    conn.commit()
    conn.close()

def get_all_tasks_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY date ASC, order_index ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def set_task_completed_db(task_id, completed=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (completed, task_id))
    conn.commit()
    conn.close()

def save_mcq_test_db(topic, questions):
    """
    questions: list of dicts:
    [{question, options, correct_answer, explanation}]
    Returns test_id
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO mcq_tests (topic, created_at, total_questions, correct_count, score_pct)
    VALUES (?, ?, ?, 0, 0.0)
    """, (topic, now, len(questions)))
    test_id = cursor.lastrowid
    
    for q in questions:
        options = json.dumps(q.get("options", []))
        cursor.execute("""
        INSERT INTO mcq_questions (test_id, question_text, options_json, correct_answer, explanation)
        VALUES (?, ?, ?, ?, ?)
        """, (test_id, q.get("question"), options, q.get("correct_answer", 0), q.get("explanation", "")))
        
    conn.commit()
    conn.close()
    return test_id

def get_mcq_test_db(test_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mcq_tests WHERE id = ?", (test_id,))
    test_row = cursor.fetchone()
    if not test_row:
        conn.close()
        return None
    test_dict = dict(test_row)
    cursor.execute("SELECT * FROM mcq_questions WHERE test_id = ? ORDER BY id ASC", (test_id,))
    q_rows = cursor.fetchall()
    conn.close()
    
    questions = []
    for r in q_rows:
        qd = dict(r)
        qd["question"] = qd.get("question_text", "")
        try:
            qd["options"] = json.loads(qd["options_json"])
        except Exception:
            qd["options"] = []
        questions.append(qd)
    test_dict["questions"] = questions
    return test_dict

def update_mcq_test_results_db(test_id, user_answers):
    """
    user_answers: dict mapping question_id (int or str) or question index -> chosen option index (int)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mcq_questions WHERE test_id = ? ORDER BY id ASC", (test_id,))
    questions = cursor.fetchall()
    
    correct_count = 0
    total = len(questions)
    
    for idx, q in enumerate(questions):
        qid = q["id"]
        correct_ans = int(q["correct_answer"])
        
        # Flexibly match key from user_answers dictionary
        chosen = -1
        for candidate_key in [str(qid), qid, str(idx + 1), idx + 1, str(idx), idx]:
            if candidate_key in user_answers:
                try:
                    chosen = int(user_answers[candidate_key])
                    break
                except Exception:
                    pass
                    
        is_corr = 1 if (chosen != -1 and chosen == correct_ans) else 0
        if is_corr:
            correct_count += 1
            
        cursor.execute("""
        UPDATE mcq_questions SET user_answer = ?, is_correct = ? WHERE id = ?
        """, (chosen, is_corr, qid))
        
    score_pct = round((correct_count / total * 100.0), 1) if total > 0 else 0.0
    cursor.execute("""
    UPDATE mcq_tests SET correct_count = ?, score_pct = ? WHERE id = ?
    """, (correct_count, score_pct, test_id))
    
    conn.commit()
    conn.close()
    return {"total": total, "correct": correct_count, "score_pct": score_pct}

def get_test_history_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mcq_tests ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_memory_db(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO agent_memory (key, value, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (key, str(value), now))
    conn.commit()
    conn.close()

def get_memory_db(key, default=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM agent_memory WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["value"]
    return default

def reset_all_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exam_info")
    cursor.execute("DELETE FROM topics")
    cursor.execute("DELETE FROM tasks")
    cursor.execute("DELETE FROM mcq_tests")
    cursor.execute("DELETE FROM mcq_questions")
    cursor.execute("DELETE FROM agent_memory")
    conn.commit()
    conn.close()
