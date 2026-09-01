import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    AVAILABLE_TOOLS, get_exam_info, get_topics, get_current_schedule,
    get_today_tasks, get_topic_progress, get_test_history, create_study_plan,
    update_study_plan, mark_task_complete, change_daily_hours, generate_mcq,
    evaluate_test, analyze_performance, update_topic_priority, save_memory
)

load_dotenv()

# List of tool functions to pass to Gemini
TOOL_FUNCTIONS = [
    get_exam_info, get_topics, get_current_schedule, get_today_tasks,
    get_topic_progress, get_test_history, create_study_plan, update_study_plan,
    mark_task_complete, change_daily_hours, generate_mcq, evaluate_test,
    analyze_performance, update_topic_priority, save_memory
]

def run_agent_loop(user_input: str):
    """
    Executes the Agentic AI loop using Gemini API tool calling.
    
    Returns dict:
    {
        "response": str (final textual response),
        "tool_calls": list of dicts [{"tool": name, "args": args, "result": result}]
    }
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    executed_tools_log = []

    if not api_key or api_key == "your_api_key_here":
        # Heuristic fallback for offline/demo without API key
        return run_heuristic_agent_fallback(user_input)

    try:
        client = genai.Client(api_key=api_key)
        
        # Build contents conversation
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_input)]
            )
        ]
        
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=TOOL_FUNCTIONS,
            temperature=0.2
        )
        
        # Multi-step tool loop max 5 steps
        for step in range(5):
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
            
            # Check if Gemini requested function calls
            function_calls = response.function_calls
            if function_calls:
                # Add model response to history
                contents.append(response.candidates[0].content)
                
                tool_response_parts = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = fc.args if fc.args else {}
                    
                    # Execute tool in Python
                    if fn_name in AVAILABLE_TOOLS:
                        try:
                            tool_result = AVAILABLE_TOOLS[fn_name](**fn_args)
                        except Exception as err:
                            tool_result = {"error": str(err)}
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' not found."}
                        
                    executed_tools_log.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result": tool_result
                    })
                    
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": tool_result}
                        )
                    )
                
                # Append tool execution output back to conversation history
                contents.append(types.Content(role="user", parts=tool_response_parts))
            else:
                # If Gemini returned text without calling tools on turn 1, run tool fallback to ensure tools execute
                if not executed_tools_log:
                    fallback_res = run_heuristic_agent_fallback(user_input)
                    return {
                        "response": response.text or fallback_res["response"],
                        "tool_calls": fallback_res["tool_calls"]
                    }
                final_text = response.text or "Completed request."
                return {
                    "response": final_text,
                    "tool_calls": executed_tools_log
                }
                
        return {
            "response": response.text or "Processed multi-step tool calls successfully.",
            "tool_calls": executed_tools_log
        }
        
    except Exception as e:
        print(f"Gemini Tool Calling Loop error: {e}. Running fallback execution.")
        fallback_res = run_heuristic_agent_fallback(user_input)
        fallback_res["error"] = str(e)
        return fallback_res

def run_heuristic_agent_fallback(user_input: str):
    """
    Deterministic Agent fallback if Gemini API is unreachable or key is unconfigured.
    Examines user intent, calls corresponding Python tools, and returns state-aware result.
    """
    text_lower = user_input.lower()
    executed_tools_log = []
    
    # 1. Check for hour/time capacity adjustment intent first
    import re
    hour_match = re.search(r'(\d+(\.\d+)?)\s*hour', text_lower)
    if hour_match or ("change" in text_lower and "hour" in text_lower) or ("set" in text_lower and "hour" in text_lower):
        hours = float(hour_match.group(1)) if hour_match else 2.0
        c_res = change_daily_hours(hours)
        executed_tools_log.append({"tool": "change_daily_hours", "args": {"hours": hours}, "result": c_res})
        resp = f"I've updated your daily study target to {hours} hours/day and dynamically re-balanced your future study schedule."

    elif "today" in text_lower or "what should i study" in text_lower:
        t_res = get_today_tasks()
        executed_tools_log.append({"tool": "get_today_tasks", "args": {}, "result": t_res})
        if not t_res:
            resp = "You have no pending tasks scheduled for today. Check your full schedule or start an MCQ test!"
        else:
            task_lines = [f"• {t['task_type']} {t['topic_name']} ({t['duration_hours']}h) [{'Completed' if t['completed'] else 'Pending'}]" for t in t_res]
            resp = "Here is your plan for today:\n" + "\n".join(task_lines)

    elif "weak" in text_lower or "scored" in text_lower or "badly" in text_lower or "poor" in text_lower:
        # Identify topic if mentioned
        topics = get_topics()
        mentioned_topic = "Graphs"
        for t in topics:
            if t["name"].lower() in text_lower:
                mentioned_topic = t["name"]
                break
                
        p_res = update_topic_priority(mentioned_topic, "VERY HIGH")
        u_res = update_study_plan()
        executed_tools_log.append({"tool": "update_topic_priority", "args": {"topic": mentioned_topic, "priority": "VERY HIGH"}, "result": p_res})
        executed_tools_log.append({"tool": "update_study_plan", "args": {}, "result": u_res})
        resp = f"I noticed you found {mentioned_topic} challenging. I increased its priority to VERY HIGH and added revision and extra practice sessions to your schedule."

    elif "test" in text_lower or "quiz" in text_lower or "mcq" in text_lower:
        m_res = generate_mcq("Graphs", "medium", 5)
        executed_tools_log.append({"tool": "generate_mcq", "args": {"topic": "Graphs", "difficulty": "medium", "count": 5}, "result": m_res})
        resp = f"I generated a 5-question test on Graphs (Test ID #{m_res['test_id']}). You can take it now!"

    elif "completed" in text_lower or "done" in text_lower or "finish" in text_lower:
        today_tasks = get_today_tasks()
        if today_tasks:
            target_id = today_tasks[0]["id"]
            m_res = mark_task_complete(target_id)
            executed_tools_log.append({"tool": "mark_task_complete", "args": {"task_id": target_id}, "result": m_res})
            resp = f"Great work! Marked '{today_tasks[0]['topic_name']}' task as completed."
        else:
            resp = "No active pending task found for today to mark complete."
    else:
        info = get_exam_info()
        topics = get_topics()
        executed_tools_log.append({"tool": "get_exam_info", "args": {}, "result": info})
        executed_tools_log.append({"tool": "get_topics", "args": {}, "result": len(topics)})
        resp = f"I am ready to assist with your '{info.get('subject', 'Exam')}' prep! Ask me what to study today, tell me your test scores, or adjust your study hours."

    return {
        "response": resp,
        "tool_calls": executed_tools_log
    }
