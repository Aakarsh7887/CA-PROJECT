import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()

class TopicAnalysis(BaseModel):
    name: str
    difficulty: str = Field(description="Low, Medium, High, or Very High")
    est_hours: float = Field(description="Estimated study hours needed, e.g., 3.0 to 8.0")
    priority: str = Field(description="LOW, MEDIUM, HIGH, or VERY HIGH")
    subtopics: list[str] = Field(default_factory=list, description="3-4 key subtopics or concepts covered in this topic")
    prerequisites: list[str] = Field(default_factory=list, description="List of prerequisite topic names from syllabus")
    notes: str = Field(default="", description="Brief study tip or reasoning for priority")

class SyllabusAnalysisResult(BaseModel):
    subject: str
    topics: list[TopicAnalysis]

DEFAULT_SUBTOPICS_MAP = {
    "Arrays": ["Offset Memory Access", "Linear & Binary Search", "Two Pointers Technique", "Sliding Window"],
    "Linked Lists": ["Singly & Doubly Linked Lists", "Pointer Operations", "Floyd's Cycle Detection", "Reversing a LinkedList"],
    "Stacks": ["LIFO Operations", "Array & LinkedList Implementation", "Balanced Parentheses", "Postfix Evaluation"],
    "Queues": ["FIFO Operations", "Circular Queue", "Priority Queue", "Deque Implementation"],
    "Stacks and Queues": ["LIFO vs FIFO", "Queue using Stacks", "Monotonic Stack", "Priority Queue"],
    "Trees": ["Binary Search Tree (BST)", "Tree Traversals (In/Pre/Post)", "Height & Depth", "AVL Tree Balancing"],
    "Graphs": ["Adjacency Matrix & List", "BFS Traversal", "DFS Traversal", "Dijkstra & Topological Sort"],
    "Dynamic Programming": ["Overlapping Subproblems", "Optimal Substructure", "Memoization (Top-Down)", "Tabulation (Bottom-Up)"],
    "Greedy Algorithms": ["Greedy Choice Property", "Activity Selection", "Huffman Coding", "Kruskal / Prim Spanning Tree"],
    "Sorting": ["Bubble/Insertion Sort", "Merge Sort & Divide-and-Conquer", "Quick Sort Partitioning", "Heap Sort O(n log n)"],
    "Searching": ["Linear Search O(n)", "Binary Search O(log n)", "Ternary Search", "Hash Map Lookups O(1)"]
}

def analyze_syllabus_with_gemini(subject: str, syllabus_text: str):
    """
    Uses Gemini API to analyze the syllabus and automatically infer topic difficulty,
    study hours needed, priority, subtopics, and prerequisites.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Extract topics list from input text
    raw_topics = [line.strip() for line in syllabus_text.strip().split("\n") if line.strip()]
    if not raw_topics:
        raw_topics = ["General Concepts"]

    if api_key and api_key != "your_api_key_here":
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""
You are an expert exam planner and curriculum designer.
Analyze the following syllabus for the subject: "{subject}".

Syllabus Topics:
{json.dumps(raw_topics, indent=2)}

For EACH topic listed above:
1. Estimate difficulty level: 'Low', 'Medium', 'High', or 'Very High'.
2. Estimate total study hours needed (e.g. 2.0 to 8.0 hours depending on complexity).
3. Determine priority level: 'LOW', 'MEDIUM', 'HIGH', or 'VERY HIGH'. Higher priority for complex/core foundational topics.
4. Provide 3-4 key subtopics or specific concepts covered in this topic.
5. Identify prerequisites among the given topics.
6. Add a short 1-line note explaining why this priority/difficulty was chosen.

Return the result matching the structured JSON schema.
"""
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SyllabusAnalysisResult,
                    temperature=0.2
                )
            )
            
            if response.text:
                data = json.loads(response.text)
                analyzed_topics = data.get("topics", [])
                if analyzed_topics:
                    for t in analyzed_topics:
                        if not t.get("subtopics"):
                            t["subtopics"] = DEFAULT_SUBTOPICS_MAP.get(t["name"], ["Core Concepts", "Problem Solving", "Key Algorithms"])
                    return analyzed_topics
        except Exception as e:
            print(f"Gemini API Syllabus Analysis error: {e}. Falling back to heuristic analysis.")
    
    # Deterministic heuristic fallback if API key is not configured or fails
    fallback_topics = []
    default_difficulties = ["Medium", "Medium", "High", "Very High", "High", "Low", "Medium"]
    default_priorities = ["MEDIUM", "MEDIUM", "HIGH", "VERY HIGH", "HIGH", "LOW", "MEDIUM"]
    
    for i, name in enumerate(raw_topics):
        diff = default_difficulties[i % len(default_difficulties)]
        prio = default_priorities[i % len(default_priorities)]
        est = 3.0
        if any(w in name.lower() for w in ["graph", "dynamic", "tree", "advanced", "concurrency", "security"]):
            diff = "Very High"
            prio = "VERY HIGH"
            est = 6.0
        elif any(w in name.lower() for w in ["stack", "queue", "list", "array", "intro", "sorting"]):
            diff = "Medium"
            prio = "MEDIUM"
            est = 3.0
            
        subtopics = DEFAULT_SUBTOPICS_MAP.get(name, ["Core Concepts", "Problem Solving", "Key Algorithms", "Complexity Analysis"])
        
        fallback_topics.append({
            "name": name,
            "difficulty": diff,
            "est_hours": est,
            "priority": prio,
            "subtopics": subtopics,
            "prerequisites": [raw_topics[i-1]] if i > 0 else [],
            "notes": f"Estimated based on foundational complexity of {name}."
        })
        
    return fallback_topics
