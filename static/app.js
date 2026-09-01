let currentDashboardData = null;
let activeTestQuestions = [];
let activeTestId = null;

document.addEventListener("DOMContentLoaded", () => {
    loadDashboard();
});

// Show/Hide Loading Overlay
function showLoading(msg = "Gemini AI is analyzing & reasoning...") {
    document.getElementById("loadingText").innerText = msg;
    document.getElementById("loadingOverlay").style.display = "flex";
}

function hideLoading() {
    document.getElementById("loadingOverlay").style.display = "none";
}

// Load Dashboard State from Server
async function loadDashboard() {
    try {
        const res = await fetch("/api/dashboard");
        const data = await res.json();
        currentDashboardData = data;

        if (!data.has_setup) {
            document.getElementById("setupSection").style.display = "block";
            document.getElementById("dashboardSection").style.display = "none";
            document.getElementById("headerStatus").style.display = "none";
            document.getElementById("btnSettings").style.display = "none";
            document.getElementById("btnReset").style.display = "none";
            
            // Set default date to 20 days in future if empty
            if (!document.getElementById("examDate").value) {
                const defaultDate = new Date();
                defaultDate.setDate(defaultDate.getDate() + 20);
                document.getElementById("examDate").value = defaultDate.toISOString().split("T")[0];
            }
            return;
        }

        // Display Dashboard
        document.getElementById("setupSection").style.display = "none";
        document.getElementById("dashboardSection").style.display = "block";
        document.getElementById("headerStatus").style.display = "flex";
        document.getElementById("btnSettings").style.display = "inline-flex";
        document.getElementById("btnReset").style.display = "inline-flex";

        // Render Navbar Badges
        document.getElementById("navSubject").innerText = data.exam_info.subject;
        document.getElementById("navCountdown").innerHTML = `<i class="fa-regular fa-clock"></i> ${data.days_remaining} Days Left`;

        // Render Stats
        document.getElementById("statCountdown").innerText = `${data.days_remaining} days`;
        document.getElementById("statProgress").innerText = `${data.overall_progress}%`;
        document.getElementById("statProgressBar").style.width = `${data.overall_progress}%`;
        document.getElementById("statDailyHours").innerText = `${data.exam_info.daily_hours}h/day`;

        // Render AI Recommendation
        document.getElementById("aiRecText").innerText = data.ai_recommendation || "Maintain your daily study targets!";
        if (data.last_replan_reason) {
            document.getElementById("aiRecFooter").style.display = "block";
            document.getElementById("replanReasonTag").innerText = data.last_replan_reason;
        } else {
            document.getElementById("aiRecFooter").style.display = "none";
        }

        // Render Today's Plan Checklist
        renderTodayPlan(data.today_plan);

        // Render Weak Topics
        renderWeakTopics(data.weak_topics);

        // Render Test History
        renderTestHistory(data.recent_tests);

        // Render Full Schedule
        renderFullSchedule(data.all_schedule);

        // Render Topic Dropdown for MCQ Test
        renderTopicOptions(data.all_topics);

        // Check if today's tasks are all completed and trigger celebration popup
        const todayStr = new Date().toISOString().split('T')[0];
        const todayTasks = (data.all_schedule || []).filter(t => t.date === todayStr);
        const todayUncompleted = todayTasks.filter(t => !t.completed);

        if (isCompletingTask && todayTasks.length > 0 && todayUncompleted.length === 0) {
            showDayCompleteModal();
        }
        isCompletingTask = false;

    } catch (err) {
        console.error("Error loading dashboard:", err);
    }
}

// Initial Exam Setup Submission
async function submitSetup(e) {
    e.preventDefault();
    const examDate = document.getElementById("examDate").value;
    const subject = document.getElementById("subject").value;
    const syllabus = document.getElementById("syllabus").value;
    const dailyHours = parseFloat(document.getElementById("dailyHours").value);

    showLoading("Gemini AI is analyzing syllabus & generating schedule...");
    try {
        const res = await fetch("/api/setup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                exam_date: examDate,
                subject: subject,
                syllabus: syllabus,
                daily_hours: dailyHours
            })
        });
        const data = await res.json();
        hideLoading();

        if (data.status === "success") {
            await loadDashboard();
        } else {
            alert(data.message || "Setup failed.");
        }
    } catch (err) {
        hideLoading();
        alert("An error occurred during setup.");
    }
}

// Render Today's Tasks
function renderTodayPlan(tasks) {
    const container = document.getElementById("todayTaskList");
    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<li class="empty-state">No pending tasks for today. Great job!</li>';
        return;
    }

    container.innerHTML = tasks.map(t => {
        const subtopicPills = parseSubtopics(t.subtopics).map(s => `<span class="subtopic-pill">${escapeHtml(s)}</span>`).join("");
        return `
            <li class="task-item ${t.completed ? 'completed' : ''}">
                <div class="task-left">
                    <input type="checkbox" class="task-checkbox" ${t.completed ? 'checked' : ''} onchange="toggleTaskComplete(${t.id}, ${t.completed})">
                    <div>
                        <strong>${escapeHtml(t.topic_name)}</strong>
                        <div class="text-muted" style="font-size: 0.8rem;">${t.duration_hours} hours • ${t.date}</div>
                        ${subtopicPills ? `<div class="sched-subtopics-box" style="margin-top: 0.3rem;">${subtopicPills}</div>` : ''}
                    </div>
                </div>
                <span class="task-tag tag-${t.task_type.toLowerCase()}">${t.task_type}</span>
            </li>
        `;
    }).join("");
}

let isCompletingTask = false;

async function toggleTaskComplete(taskId, currentStatus) {
    const newStatus = currentStatus ? 0 : 1;
    if (newStatus === 1) {
        isCompletingTask = true;
    }
    await fetch(`/api/tasks/${taskId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: newStatus })
    });
    await loadDashboard();
}

function showDayCompleteModal() {
    const modal = document.getElementById("dayCompleteModal");
    if (modal) modal.style.display = "flex";
}

function closeDayCompleteModal() {
    const modal = document.getElementById("dayCompleteModal");
    if (modal) modal.style.display = "none";
}

function startTestFromModal() {
    closeDayCompleteModal();
    switchTab('test');
}

// Render Full Schedule Date-Grouped Cards
function renderFullSchedule(tasks) {
    const container = document.getElementById("scheduleCardsContainer");
    if (!container) return;

    if (!tasks || tasks.length === 0) {
        container.innerHTML = '<div class="card"><div class="empty-state">No study schedule generated yet.</div></div>';
        return;
    }

    // Group tasks by date
    const dateMap = {};
    tasks.forEach(t => {
        if (!dateMap[t.date]) dateMap[t.date] = [];
        dateMap[t.date].push(t);
    });

    const sortedDates = Object.keys(dateMap).sort();

    container.innerHTML = sortedDates.map(dateStr => {
        const dateTasks = dateMap[dateStr];
        const totalHours = dateTasks.reduce((sum, t) => sum + parseFloat(t.duration_hours), 0).toFixed(1);
        const formattedDate = formatDateHeader(dateStr);

        const taskCardsHtml = dateTasks.map(t => {
            const subtopicsList = parseSubtopics(t.subtopics);
            const subtopicsHtml = subtopicsList.map(s => `<span class="subtopic-pill">${escapeHtml(s)}</span>`).join("");

            return `
                <div class="sched-task-card ${t.completed ? 'completed' : ''}">
                    <div class="sched-task-card-top">
                        <span class="task-tag tag-${t.task_type.toLowerCase()}">${t.task_type}</span>
                        <span class="sched-task-duration"><i class="fa-regular fa-clock"></i> ${t.duration_hours}h</span>
                    </div>

                    <div class="sched-task-topic">${escapeHtml(t.topic_name)}</div>

                    <div class="sched-subtopics-box">
                        ${subtopicsHtml || '<span class="subtopic-pill">Core Concepts</span>'}
                    </div>

                    <div class="sched-task-footer">
                        <label class="task-check-label">
                            <input type="checkbox" ${t.completed ? 'checked' : ''} onchange="toggleTaskComplete(${t.id}, ${t.completed})">
                            <span>${t.completed ? 'Completed ✓' : 'Mark Done'}</span>
                        </label>
                    </div>
                </div>
            `;
        }).join("");

        return `
            <div class="date-group-card">
                <div class="date-group-header">
                    <div class="date-title-box">
                        <i class="fa-regular fa-calendar-days text-primary" style="font-size: 1.2rem;"></i>
                        <span class="date-title-text">${formattedDate}</span>
                    </div>
                    <span class="date-task-summary">${dateTasks.length} Tasks • ${totalHours} Hours</span>
                </div>

                <div class="date-tasks-grid">
                    ${taskCardsHtml}
                </div>
            </div>
        `;
    }).join("");
}

function parseSubtopics(subtopicsStr) {
    if (!subtopicsStr) return [];
    if (Array.isArray(subtopicsStr)) return subtopicsStr;
    return subtopicsStr.split(",").map(s => s.trim()).filter(s => s.length > 0);
}

function formatDateHeader(dateStr) {
    try {
        const parts = dateStr.split("-");
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        const options = { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' };
        return d.toLocaleDateString('en-US', options);
    } catch (e) {
        return dateStr;
    }
}

// Render Topic Options for MCQ Test
function renderTopicOptions(topics) {
    const select = document.getElementById("testTopicSelect");
    if (!select) return;

    let optionsHtml = '<option value="General">All Topics (General)</option>';
    if (topics && topics.length > 0) {
        optionsHtml += topics.map(t => {
            const topicName = typeof t === "string" ? t : (t.name || t.topic_name || "General");
            const prof = (typeof t === "object" && t.proficiency !== undefined) ? ` (Proficiency: ${t.proficiency}%)` : '';
            return `<option value="${escapeHtml(topicName)}">${escapeHtml(topicName)}${prof}</option>`;
        }).join("");
    }

    select.innerHTML = optionsHtml;
}

// Tab Switching
function switchTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    if (tabName === 'dashboard') {
        document.querySelectorAll(".tab-btn")[0].classList.add("active");
        document.getElementById("tabDashboard").classList.add("active");
    } else if (tabName === 'schedule') {
        document.querySelectorAll(".tab-btn")[1].classList.add("active");
        document.getElementById("tabSchedule").classList.add("active");
        if (currentDashboardData && currentDashboardData.all_schedule) {
            renderFullSchedule(currentDashboardData.all_schedule);
        }
    } else if (tabName === 'test') {
        document.querySelectorAll(".tab-btn")[2].classList.add("active");
        document.getElementById("tabTest").classList.add("active");
        if (currentDashboardData && currentDashboardData.all_topics) {
            renderTopicOptions(currentDashboardData.all_topics);
        }
    }
}

// Chat Assistant Implementation
function sendQuickPrompt(promptText) {
    document.getElementById("chatInput").value = promptText;
    submitChat(new Event("submit"));
}

async function submitChat(e) {
    e.preventDefault();
    const input = document.getElementById("chatInput");
    const msgText = input.value.trim();
    if (!msgText) return;

    input.value = "";
    const chatContainer = document.getElementById("chatMessages");

    // Append User Message
    chatContainer.innerHTML += `
        <div class="chat-message user">
            <div class="msg-bubble">${escapeHtml(msgText)}</div>
        </div>
    `;
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Show Assistant Thinking Indicator
    const thinkingId = "thinking_" + Date.now();
    chatContainer.innerHTML += `
        <div class="chat-message assistant" id="${thinkingId}">
            <div class="msg-bubble"><i class="fa-solid fa-spinner fa-spin"></i> Reasoning & selecting tools...</div>
        </div>
    `;
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: msgText })
        });
        const data = await res.json();

        const thinkingElem = document.getElementById(thinkingId);
        if (thinkingElem) thinkingElem.remove();

        // Render Assistant Response + Tool Calls Badges
        let toolPillsHtml = "";
        if (data.tool_calls && data.tool_calls.length > 0) {
            toolPillsHtml = `
                <div class="tool-calls-container">
                    ${data.tool_calls.map(tc => `
                        <div class="tool-call-pill">
                            <i class="fa-solid fa-gears"></i> Executed Python Tool: <strong>${tc.tool}()</strong>
                        </div>
                    `).join("")}
                </div>
            `;
        }

        chatContainer.innerHTML += `
            <div class="chat-message assistant">
                <div class="msg-bubble">
                    ${escapeHtml(data.response)}
                    ${toolPillsHtml}
                </div>
            </div>
        `;
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // Reload dashboard state as agent tools may have mutated DB schedule/state!
        await loadDashboard();

    } catch (err) {
        console.error("Chat error:", err);
    }
}

// MCQ Test Functionality
async function startMCQTest() {
    const topic = document.getElementById("testTopicSelect").value;
    const count = document.getElementById("testCountSelect").value;

    showLoading(`Gemini AI is generating ${count} MCQs on ${topic}...`);
    try {
        const res = await fetch("/api/mcq/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic, difficulty: "medium", count })
        });
        const data = await res.json();
        hideLoading();

        activeTestId = data.test_id;
        activeTestQuestions = data.questions;

        // Display Test Player
        document.getElementById("testLauncherCard").style.display = "none";
        document.getElementById("testResultCard").style.display = "none";
        document.getElementById("testPlayerCard").style.display = "block";

        document.getElementById("activeTestTopicTag").innerText = topic;
        document.getElementById("activeTestProgress").innerText = `${data.questions.length} Questions`;

        renderMCQForm(data.questions);

    } catch (err) {
        hideLoading();
        alert("Failed to generate MCQ test.");
    }
}

function renderMCQForm(questions) {
    const container = document.getElementById("mcqQuestionsContainer");
    container.innerHTML = questions.map((q, idx) => {
        const qKey = q.id ? q.id : (idx + 1);
        const qText = q.question_text || q.question;
        return `
            <div class="mcq-q-card">
                <div class="mcq-q-title">Q${idx + 1}: ${escapeHtml(qText)}</div>
                <div>
                    ${q.options.map((opt, optIdx) => `
                        <label class="mcq-option-label">
                            <input type="radio" name="q_${qKey}" value="${optIdx}" required>
                            <span>${escapeHtml(opt)}</span>
                        </label>
                    `).join("")}
                </div>
            </div>
        `;
    }).join("");
}

async function submitMCQTest(e) {
    e.preventDefault();
    const userAnswers = {};

    activeTestQuestions.forEach((q, idx) => {
        const qKey = q.id ? q.id : (idx + 1);
        const selected = document.querySelector(`input[name="q_${qKey}"]:checked`);
        if (selected) {
            userAnswers[qKey] = parseInt(selected.value);
            // Also add by 1-based index and 0-based index for fallback matching
            userAnswers[idx + 1] = parseInt(selected.value);
            userAnswers[idx] = parseInt(selected.value);
        }
    });

    showLoading("Performance Agent is evaluating test & analyzing weak topics...");
    try {
        const res = await fetch("/api/mcq/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ test_id: activeTestId, user_answers: userAnswers })
        });
        const data = await res.json();
        hideLoading();

        // Display Test Results & Detailed Explanations
        document.getElementById("testPlayerCard").style.display = "none";
        document.getElementById("testResultCard").style.display = "block";

        const scoreSum = data.score_summary;
        document.getElementById("resultScoreBadge").innerText = `${scoreSum.correct}/${scoreSum.total} (${scoreSum.score_pct}%)`;

        const perf = data.performance_analysis;
        let breakdownHtml = `
            <div class="card ai-recommendation-card mb-3">
                <h4><i class="fa-solid fa-robot"></i> Performance Agent Insight</h4>
                <p>${escapeHtml(perf.recommendation)}</p>
            </div>
        `;

        if (data.test_details && data.test_details.questions) {
            breakdownHtml += data.test_details.questions.map((q, idx) => `
                <div class="mcq-q-card">
                    <div class="mcq-q-title">Q${idx + 1}: ${escapeHtml(q.question_text || q.question)}</div>
                    <div>
                        ${q.options.map((opt, optIdx) => {
                            let optionClass = "";
                            let tagText = "";
                            const isCorrectChoice = (optIdx === intVal(q.correct_answer));
                            const isUserChoice = (optIdx === intVal(q.user_answer));

                            if (isCorrectChoice && isUserChoice) {
                                optionClass = "correct-choice";
                                tagText = '<span class="text-success"> (Your Answer ✓)</span>';
                            } else if (isCorrectChoice) {
                                optionClass = "correct-choice";
                                tagText = '<span class="text-success"> (Correct Answer)</span>';
                            } else if (isUserChoice) {
                                optionClass = "incorrect-choice";
                                tagText = '<span class="text-danger"> (Your Choice ✗)</span>';
                            }

                            return `
                                <div class="mcq-option-label ${optionClass}">
                                    <span>${escapeHtml(opt)}</span>
                                    ${tagText}
                                </div>
                            `;
                        }).join("")}
                    </div>
                    <div class="explanation-box">
                        <strong>Explanation:</strong> ${escapeHtml(q.explanation)}
                    </div>
                </div>
            `).join("");
        }

        document.getElementById("resultBreakdown").innerHTML = breakdownHtml;

        // Refresh dashboard state
        await loadDashboard();

    } catch (err) {
        hideLoading();
        alert("Failed to submit test.");
    }
}

function intVal(val) {
    if (val === undefined || val === null) return -1;
    return parseInt(val);
}

function cancelTest() {
    resetTestView();
}

function resetTestView() {
    document.getElementById("testPlayerCard").style.display = "none";
    document.getElementById("testResultCard").style.display = "none";
    document.getElementById("testLauncherCard").style.display = "block";
}

// Settings Modal
function openSettingsModal() {
    if (currentDashboardData && currentDashboardData.exam_info) {
        document.getElementById("settingsDailyHours").value = currentDashboardData.exam_info.daily_hours;
    }
    document.getElementById("settingsModal").style.display = "flex";
}

function closeSettingsModal() {
    document.getElementById("settingsModal").style.display = "none";
}

async function saveSettingsHours() {
    const hours = parseFloat(document.getElementById("settingsDailyHours").value);
    showLoading("Updating daily study target & re-balancing schedule...");
    try {
        await fetch("/api/settings/hours", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ daily_hours: hours })
        });
        hideLoading();
        closeSettingsModal();
        await loadDashboard();
    } catch (err) {
        hideLoading();
        alert("Failed to update settings.");
    }
}

async function triggerManualReplan() {
    showLoading("Adaptive Replanner is re-balancing study schedule...");
    try {
        await fetch("/api/settings/hours", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ daily_hours: currentDashboardData.exam_info.daily_hours })
        });
        hideLoading();
        await loadDashboard();
    } catch (err) {
        hideLoading();
    }
}

async function confirmReset() {
    if (confirm("Are you sure you want to reset all exam data and start a new setup?")) {
        showLoading("Resetting all stored data...");
        await fetch("/api/reset", { method: "POST" });
        hideLoading();
        await loadDashboard();
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
