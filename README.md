# Agentic AI Exam Preparation Assistant

An intelligent, autonomous **Agentic AI Exam Preparation Assistant** built using **Python**, Google's official **`google-genai` SDK (Gemini API)**, **Flask**, and **SQLite**.

Unlike basic chat widgets, this application demonstrates genuine **Agentic AI behavior**: Gemini acts as a reasoning engine that observes persistent database state, selects and invokes native Python tools, updates memory, and dynamically re-plans study schedules based on student performance.

---

## 🌟 Why This Is Agentic AI

This application is **not just an LLM chatbot**. Simply sending prompts to Gemini and displaying responses is not agentic. 

This system is genuinely **Agentic** because it implements an autonomous **Observe → Reason → Plan → Act → Reflect** loop:

```text
       ┌────────────────────────────────────────────────────────┐
       │                     PERSISTENT STATE                  │
       │  (Exam Date, Topics, Proficiency, Past Scores, Schedule)│
       └───────────────────────────┬────────────────────────────┘
                                   │ OBSERVE
                                   ▼
                       ┌───────────────────────┐
                       │     Gemini Agent      │
                       │   Reasoning Engine    │
                       └───────────┬───────────┘
                                   │ PLAN & SELECT TOOLS
                                   ▼
                       ┌───────────────────────┐
                       │   Native Python Tools │
                       │ (replan, grade, update│
                       │  priority, save memory│
                       └───────────┬───────────┘
                                   │ ACT & UPDATE DB
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                   DYNAMIC ADAPTATION                   │
       │ (Auto-rebalances schedule, flags weak areas, advises)  │
       └────────────────────────────────────────────────────────┘
```

1. **State Observation**: The agent reads real user history, topic proficiency scores, completed tasks, and remaining days from SQLite storage.
2. **Autonomous Tool Selection**: Gemini is equipped with real Python function declarations (`get_today_tasks`, `change_daily_hours`, `update_topic_priority`, `update_study_plan`, `generate_mcq`, etc.) and dynamically decides *which* tools to invoke.
3. **Multi-Step Execution**: Supports sequential tool execution within a single turn (e.g. `get_topic_progress("Graphs")` → `update_topic_priority("Graphs", "VERY HIGH")` → `update_study_plan()` → `save_memory()`).
4. **Adaptive Replanning**: When a student performs poorly in an MCQ test (<50%), the Performance Agent automatically elevates topic priority, injects revision and practice sessions, shifts lower-priority topics, and logs the reasoning.
5. **Persistent Memory**: Decisions, topic proficiencies, and schedule changes persist across application restarts.

---

## 🚀 Key Capabilities

### 1. AI Syllabus Planner
- Takes simple user inputs: **Exam Date**, **Subject**, and **Syllabus** (list or multiline text).
- Automatically infers topic difficulty, estimated study time, priority level, and prerequisite dependencies.
- Deterministically generates a day-by-day study, revision, and practice schedule based on days remaining and daily hours capacity (default: 3h/day).

### 2. Adaptive Replanner
- Re-balances future study schedules dynamically when:
  - MCQ test score drops below 50% (injects urgent revision for weak topics).
  - MCQ test score exceeds 85% (shifts focus to weaker areas).
  - Study tasks are missed or completed ahead of schedule.
  - Daily available study hours change.

### 3. AI MCQ Generator
- Uses Gemini structured JSON output to generate topic-specific multiple choice questions.
- Includes 4 distinct options, correct answer index, difficulty rating, and detailed explanations.
- Features an interactive single-question or test-runner web interface.

### 4. Performance Agent
- Evaluates test submissions deterministically in Python.
- Calculates score, accuracy %, correct/incorrect breakdown.
- Identifies specific weak sub-concepts and strong concepts.
- Automatically updates topic proficiency % and provides actionable AI study recommendations.

### 5. Natural Language Study Assistant
- Chat interface powered by Gemini function calling.
- Accepts natural language commands like *"What should I study today?"*, *"I only have 1 hour today"*, or *"I scored badly in Graphs. Fix my schedule."*
- Executes real Python tool functions with transparent tool execution pills shown in the chat window.

---

## 🛠️ Project Architecture

```text
CA PROJECT/
│
├── app.py                     # Flask web server & REST API endpoints
├── .env                       # API Key & model configuration
├── .env.example               # Template environment configuration
├── .gitignore                 # Environment & DB exclusion
├── requirements.txt           # Python dependencies
├── README.md                  # Project documentation & agentic architecture
│
├── agent/
│   ├── __init__.py
│   ├── agent.py               # Gemini tool-calling loop & multi-step execution
│   ├── prompts.py             # System prompts & agent instructions
│   └── tools.py               # 15 Python functions exposed as Agent tools
│
├── planner/
│   ├── __init__.py
│   ├── planner.py             # AI Syllabus analysis & topic estimation
│   └── scheduler.py           # Day-by-day scheduler & Adaptive Replanner
│
├── testing/
│   ├── __init__.py
│   ├── mcq_generator.py       # Gemini structured JSON MCQ generation
│   └── evaluator.py           # MCQ evaluation & Performance Agent
│
├── memory/
│   ├── __init__.py
│   └── database.py            # SQLite schema, queries, persistent state manager
│
├── templates/
│   └── index.html             # Single-page web application dashboard
│
└── static/
    ├── style.css              # Dark/light responsive CSS styling
    └── app.js                 # Frontend interactivity, API calls & tool logs
```

---

## 🧰 Available Agent Tools

The Gemini Agent has access to the following native Python tools in `agent/tools.py`:

| Tool Name | Parameters | Purpose |
|---|---|---|
| `get_exam_info()` | None | Fetch exam date, subject, and daily study capacity. |
| `get_topics()` | None | Fetch all topics with difficulty, priority, and proficiency %. |
| `get_current_schedule()` | None | Fetch full generated master schedule. |
| `get_today_tasks()` | None | Fetch study tasks scheduled for today. |
| `get_topic_progress(topic)` | `topic` | Fetch detailed progress and completion % for a topic. |
| `get_test_history()` | None | Fetch history of completed MCQ tests. |
| `create_study_plan()` | None | Generate initial master study schedule. |
| `update_study_plan()` | None | Force adaptive replanning of remaining schedule. |
| `mark_task_complete(task_id)`| `task_id` | Mark a scheduled task as completed. |
| `change_daily_hours(hours)` | `hours` | Update daily study capacity and auto-replan schedule. |
| `generate_mcq(topic, ...)` | `topic`, `difficulty`, `count` | Generate structured MCQ test. |
| `evaluate_test(test_id, ...)`| `test_id`, `user_answers` | Grade test & trigger Performance Agent. |
| `analyze_performance()` | None | Run performance analysis on recent test history. |
| `update_topic_priority(...)` | `topic`, `priority` | Set topic priority (`LOW`, `MEDIUM`, `HIGH`, `VERY HIGH`). |
| `save_memory(key, value)` | `key`, `value` | Persist key-value notes in agent memory. |

---

## ⚡ Installation & Setup

### 1. Prerequisites
- **Python 3.11+** installed.
- A **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/).

### 2. Environment Setup
Clone or navigate to the project directory:

```bash
cd "d:\CA-project-1-main\CA PROJECT"
```

Create and configure your `.env` file:

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Install Dependencies
Install packages using `pip`:

```bash
pip install -r requirements.txt
```

---

## 🏃 Running the Application

Start the Flask application server:

```bash
python app.py
```

Open your web browser and navigate to:
```text
http://localhost:5000
```

---

## 🧪 Demonstration Flow (Step-by-Step)

To demonstrate the full agentic loop:

1. **Initial Setup**:
   - **Exam Date**: Select a date (e.g., September 20, 2026).
   - **Subject**: `Data Structures and Algorithms`.
   - **Syllabus**:
     ```text
     Arrays
     Linked Lists
     Stacks and Queues
     Trees
     Graphs
     Dynamic Programming
     Greedy Algorithms
     Sorting
     Searching
     ```
   - Click **Generate AI Study Plan**. Gemini analyzes syllabus topics, estimates difficulty/priority, and Python creates a day-by-day plan.

2. **Dashboard Overview**:
   - View days remaining, overall completion progress bar, today's plan checklist, and weak topics.

3. **Take MCQ Test & Trigger Performance Agent**:
   - Navigate to **Take MCQ Test** tab.
   - Select topic **Graphs**, question count **5**, and click **Start MCQ Test**.
   - Intentionally select incorrect choices to get a low score (<50%).
   - Click **Submit Test**.
   - **Performance Agent** identifies weak sub-concepts, updates Graphs proficiency to LOW, boosts topic priority to `VERY HIGH`, and **Adaptive Replanner** automatically alters the future study plan to inject Graphs revision.

4. **Natural Language Study Assistant (Tool Calling)**:
   - Click the chat box and ask: `"What should I study today?"`
   - Observe Gemini call `get_today_tasks()` and return exact tasks from DB.
   - Type: `"I only have 1 hour today."`
   - Observe Gemini call `change_daily_hours(1.0)` and re-balance future days.
   - Type: `"I scored badly in Graphs. Fix my schedule."`
   - Observe Gemini perform sequential tool calls: `update_topic_priority("Graphs", "VERY HIGH")` → `update_study_plan()` → `save_memory()`.

---

## 🛡️ License & Credits
Built using Python, Google's `google-genai` SDK, Flask, and SQLite. Designed for demonstrating real Agentic AI concepts.
