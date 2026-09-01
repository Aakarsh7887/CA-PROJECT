import os
import unittest
from datetime import datetime, timedelta

# Import modules to test
from memory.database import (
    init_db, save_exam_info, get_exam_info_db, save_topics_db,
    get_topics_db, save_tasks_db, get_all_tasks_db, reset_all_data,
    set_task_completed_db
)
from planner.planner import analyze_syllabus_with_gemini
from planner.scheduler import generate_initial_schedule, replan_schedule
from testing.mcq_generator import generate_mcq
from testing.evaluator import evaluate_test, analyze_performance
from agent.tools import AVAILABLE_TOOLS
from agent.agent import run_agent_loop

class TestExamPrepAssistant(unittest.TestCase):

    def setUp(self):
        init_db()
        reset_all_data()

    def test_01_setup_and_planner(self):
        exam_date = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        subject = "Data Structures and Algorithms"
        syllabus = "Arrays\nLinked Lists\nStacks\nQueues\nTrees\nGraphs\nDynamic Programming"
        
        save_exam_info(exam_date, subject, 3.0)
        info = get_exam_info_db()
        self.assertIsNotNone(info)
        self.assertEqual(info["subject"], subject)
        
        topics = analyze_syllabus_with_gemini(subject, syllabus)
        self.assertTrue(len(topics) >= 7)
        save_topics_db(topics)
        
        saved_topics = get_topics_db()
        self.assertEqual(len(saved_topics), len(topics))
        
        schedule = generate_initial_schedule()
        self.assertTrue(len(schedule) > 0)
        
        tasks = get_all_tasks_db()
        self.assertEqual(len(tasks), len(schedule))
        print(f"✓ Setup & Planner Test passed. Generated {len(tasks)} study tasks.")

    def test_02_mcq_generator_and_evaluator(self):
        # Setup basic exam info
        exam_date = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")
        save_exam_info(exam_date, "Computer Science", 3.0)
        save_topics_db([
            {"name": "Graphs", "difficulty": "Very High", "priority": "MEDIUM", "est_hours": 6.0}
        ])
        generate_initial_schedule()

        # Generate MCQ test
        test_data = generate_mcq("Graphs", "medium", 3)
        self.assertIn("test_id", test_data)
        self.assertEqual(len(test_data["questions"]), 3)
        
        test_id = test_data["test_id"]
        
        # Submit poor answers (0/3 correct)
        user_answers = {
            test_data["questions"][0].get("id", 1): 9, # Incorrect choice
            test_data["questions"][1].get("id", 2): 9,
            test_data["questions"][2].get("id", 3): 9
        }
        
        eval_res = evaluate_test(test_id, user_answers)
        self.assertIn("score_summary", eval_res)
        self.assertEqual(eval_res["score_summary"]["correct"], 0)
        
        perf = eval_res["performance_analysis"]
        self.assertEqual(perf["topic"], "Graphs")
        self.assertTrue(perf["replanned"])
        
        # Verify Graphs priority was boosted to VERY HIGH in DB
        topics = get_topics_db()
        graphs_topic = [t for t in topics if t["name"].lower() == "graphs"][0]
        self.assertEqual(graphs_topic["priority"], "VERY HIGH")
        
        print("✓ MCQ Generator, Evaluator & Performance Agent Test passed.")

    def test_03_agent_tool_calling_loop(self):
        exam_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
        save_exam_info(exam_date, "Algorithms", 3.0)
        save_topics_db([
            {"name": "Arrays", "difficulty": "Medium", "priority": "MEDIUM", "est_hours": 3.0},
            {"name": "Graphs", "difficulty": "High", "priority": "HIGH", "est_hours": 5.0}
        ])
        generate_initial_schedule()

        # Test natural language command tool loop
        response = run_agent_loop("What should I study today?")
        self.assertIn("response", response)
        self.assertTrue(len(response["tool_calls"]) > 0)
        print(f"✓ Agent Tool Loop Test passed. Executed tools: {[t['tool'] for t in response['tool_calls']]}")

        # Test hours adjustment command
        res_hours = run_agent_loop("I only have 2 hours today. Adjust my schedule.")
        self.assertIn("response", res_hours)
        info = get_exam_info_db()
        self.assertEqual(info["daily_hours"], 2.0)
        print("✓ Agent Hours Adjustment Tool Test passed.")

if __name__ == "__main__":
    unittest.main()
