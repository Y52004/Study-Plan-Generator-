from flask import Flask, request, jsonify, render_template
import json
import os
from datetime import datetime
from fpdf import FPDF
from dotenv import load_dotenv
import io
import pdfplumber
from werkzeug.utils import secure_filename
import threading

# Load environment variables from .env file (safe - won't raise)
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Get API key from environment variable (do NOT exit on missing - handle gracefully)
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    # set for litellm if present
    os.environ["GEMINI_API_KEY"] = api_key

# Global in-memory store (unchanged)
study_plans = {}

# ---------------------------------------------------------------------
# Lazy initialization utilities for CrewAI/LLM/Agents
# ---------------------------------------------------------------------
_agents_lock = threading.Lock()
_agents_initialized = False
_llm_instance = None
_agent_core = None       # Agent A (syllabus + learning)
_agent_scheduler = None  # Agent B (schedule + resources)
_agent_progress = None   # Agent C (progress tracker)


def allowed_file(filename):
    """Check if file has allowed extension (PDF only)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_pdf_file(file):
    """
    Extract text content from PDF file
    """
    try:
        filename = secure_filename(file.filename)
        if not allowed_file(filename):
            raise ValueError("Invalid file type. Only PDF files are allowed. Please upload a PDF file.")

        pdf_content = io.BytesIO(file.read())
        extracted_text = ""
        page_count = 0

        with pdfplumber.open(pdf_content) as pdf:
            page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    extracted_text += f"\n--- Page {page_num} ---\n{text}"

        if not extracted_text:
            raise ValueError("No text content found in the PDF. Please provide a valid text-based PDF.")

        return extracted_text, page_count

    except Exception as e:
        # bubble up for route to handle
        raise


def _init_agents_if_needed():
    """
    Lazy init LLM + CrewAI agents. This delays heavy imports until first request.
    We combine agents into 3 to reduce memory load:
      - agent_core: syllabus analysis + learning style + resources (combined)
      - agent_scheduler: schedule creation (also covers resource mapping if needed)
      - agent_progress: progress tracking
    """
    global _agents_initialized, _llm_instance, _agent_core, _agent_scheduler, _agent_progress

    with _agents_lock:
        if _agents_initialized:
            return

        # Import heavy libraries lazily
        try:
            # litellm/libraries may be present - but import crewai components
            from crewai import Agent, Task, Crew, LLM
        except Exception as e:
            # If CrewAI or LLM classes are missing, raise a clear error
            raise RuntimeError(f"CrewAI import failed: {e}")

        # Create a single LLM instance and prefer non-native provider to reduce memory
        try:
            # Use explicit LLM object with use_native=False to avoid heavy native provider
            # If CREWAI's LLM class is different in your version, this fallback uses string
            try:
                _llm_instance = LLM(model="gemini/gemini-2.0-flash", use_native=False)
            except Exception:
                # Fallback to string (CrewAI will interpret when constructing Agent), but
                # prefer LLM object above.
                _llm_instance = "gemini/gemini-2.0-flash"
        except Exception as e:
            # If LLM creation fails (missing creds, etc.) keep _llm_instance=None and
            # handle later in request processing.
            _llm_instance = None
            app.logger.warning(f"LLM creation warning: {e}")

        # Define factory to create Agent objects but DO NOT run heavy work here
        def make_agent(role, goal, backstory):
            try:
                # If we created an LLM object, pass it; else pass model string (CrewAI will try)
                return Agent(role=role, goal=goal, backstory=backstory, llm=_llm_instance, verbose=False)
            except Exception as e:
                # If Agent creation fails (e.g., missing provider), raise an informative error.
                raise RuntimeError(f"Failed to create agent '{role}': {e}")

        # Create combined agents (these are lighter than creating 5 separate ones)
        _agent_core = make_agent(
            role="Core Study Plan Agent",
            goal="Analyze syllabus, assess learning style, and produce topic/resource mappings",
            backstory="Combines syllabus analysis and learning style assessment to produce structured topics and resource suggestions."
        )
        _agent_scheduler = make_agent(
            role="Schedule & Resource Agent",
            goal="Create day-by-day schedule and map resources to schedule sessions",
            backstory="Builds a practical schedule using provided topic breakdown and learning preferences."
        )
        _agent_progress = make_agent(
            role="Progress Tracker Agent",
            goal="Create progress checkpoints and adaptation strategies",
            backstory="Designs monitoring metrics and triggers for adapting the study plan."
        )

        _agents_initialized = True


# ---------------------------------------------------------------------
# Core study plan generation (uses the 3 agents)
# ---------------------------------------------------------------------
def create_study_plan(syllabus_text, learning_preferences, study_duration_days):
    """
    Orchestrate the 3-agent crew to produce the final study plan.
    We combine multiple responsibilities into fewer LLM calls to reduce memory use.
    """
    # Ensure agents are ready; if not, return a clean error
    try:
        _init_agents_if_needed()
    except Exception as e:
        return {"error": f"Server misconfiguration: {e}"}

    # If LLM creation failed earlier, return informative error
    if _llm_instance is None:
        return {"error": "LLM not configured or failed to initialize. Check GEMINI_API_KEY and server logs."}

    # We'll call 3 crews/tasks sequentially:
    # 1) CoreAgent -> syllabus + learning analysis -> returns syllabus_analysis & learning_analysis
    # 2) SchedulerAgent -> schedule + resources based on (1)
    # 3) ProgressAgent -> progress tracking based on (1) & (2)

    syllabus_analysis = {}
    learning_analysis = {}
    schedule = {}
    resources = {}
    progress_system = {}

    # 1) Core agent - single task to extract both syllabus analysis and learning style assessment
    try:
        from crewai import Task, Crew  # lazy import inside function
        core_description = f"""
You are an AI curriculum assistant. Input: SYLLABUS TEXT and USER LEARNING PREFERENCES.
Task: 
1) Analyze the syllabus text and return a JSON object named 'syllabus_analysis' with fields:
   - document_type
   - content_quality
   - subjects (list of {{"name","chapters":[{{"name","estimated_hours","difficulty","key_concepts"}}]}})
   - total_estimated_hours
   - prerequisites
   - learning_path_summary

2) Assess the learning preferences and return a JSON object named 'learning_analysis' with fields:
   - primary_learning_style
   - secondary_learning_styles
   - strengths
   - challenges
   - recommended_study_methods
   - personalized_tips

Return ONLY a JSON object with structure:
{{
  "syllabus_analysis": {{ ... }},
  "learning_analysis": {{ ... }}
}}
"""
        task_core = Task(
            description=core_description + f"\n\nSYLLABUS_TEXT:\n{syllabus_text}\n\nLEARNING_PREFERENCES:\n{learning_preferences}",
            expected_output="JSON with syllabus_analysis and learning_analysis",
            agent=_agent_core
        )
        crew_core = Crew(agents=[_agent_core], tasks=[task_core])
        core_result = crew_core.kickoff()
        core_text = str(core_result).strip()

        # Attempt to extract JSON block if wrapped in triple-backticks
        if core_text.startswith("```"):
            lines = core_text.splitlines()
            # try to find json block boundaries
            start_idx = 0
            end_idx = len(lines)
            for i, ln in enumerate(lines):
                if ln.strip().startswith("```json") or ln.strip() == "```":
                    start_idx = i + 1
                    break
            for j in range(start_idx, len(lines)):
                if lines[j].strip() == "```":
                    end_idx = j
                    break
            core_text = "\n".join(lines[start_idx:end_idx]).strip()

        core_json = json.loads(core_text)
        syllabus_analysis = core_json.get("syllabus_analysis", {})
        learning_analysis = core_json.get("learning_analysis", {})

    except Exception as e:
        # If Core step fails, capture the error and continue with empty placeholders
        app.logger.error(f"[Core Agent] Error: {e}")
        syllabus_analysis = {"error": str(e)}
        learning_analysis = {"error": str(e)}

    # 2) Scheduler & Resources agent
    try:
        from crewai import Task, Crew
        schedule_description = f"""
Using the following inputs (ONLY JSON output):

SYLLABUS_ANALYSIS:
{json.dumps(syllabus_analysis, indent=2)[:4000]}

LEARNING_ANALYSIS:
{json.dumps(learning_analysis, indent=2)[:2000]}

Study duration (days): {study_duration_days}

Task:
Return a JSON object with:
{{
  "schedule": [ {{ "day": 1, "date": "YYYY-MM-DD", "sessions": [{{"session","time","topic","subtopics","activities","break_after"}}] }} ],
  "weekly_milestones": ["..."],
  "resource_map": [ {{ "topic":"...", "resources":[{{"type","name","description","why_recommended"}}] }} ]
}}
"""
        task_sched = Task(
            description=schedule_description,
            expected_output="JSON schedule & resource_map",
            agent=_agent_scheduler
        )
        crew_sched = Crew(agents=[_agent_scheduler], tasks=[task_sched])
        sched_result = crew_sched.kickoff()
        sched_text = str(sched_result).strip()

        if sched_text.startswith("```"):
            lines = sched_text.splitlines()
            start_idx = 0
            end_idx = len(lines)
            for i, ln in enumerate(lines):
                if ln.strip().startswith("```json") or ln.strip() == "```":
                    start_idx = i + 1
                    break
            for j in range(start_idx, len(lines)):
                if lines[j].strip() == "```":
                    end_idx = j
                    break
            sched_text = "\n".join(lines[start_idx:end_idx]).strip()

        sched_json = json.loads(sched_text)
        schedule = sched_json.get("schedule", {})
        resources = {"resource_recommendations": sched_json.get("resource_map", [])}
    except Exception as e:
        app.logger.error(f"[Scheduler Agent] Error: {e}")
        schedule = {"error": str(e)}
        resources = {"error": str(e)}

    # 3) Progress Tracker agent
    try:
        from crewai import Task, Crew
        progress_description = f"""
Design a progress tracking JSON object for the study plan. Input:
Syllabus summary: {json.dumps(syllabus_analysis, indent=2)[:2000]}
Schedule summary: {json.dumps(schedule, indent=2)[:2000]}

Return JSON with:
{{
  "tracking_metrics": [ {{ "metric","how_to_measure","success_criteria" }} ],
  "checkpoint_schedule": [ {{ "checkpoint","day","assessment","adaptation_triggers" }} ],
  "adaptation_strategies": [ {{ "scenario","action" }} ],
  "reflection_prompts": ["..."]
}}
"""
        task_prog = Task(
            description=progress_description,
            expected_output="JSON progress tracking system",
            agent=_agent_progress
        )
        crew_prog = Crew(agents=[_agent_progress], tasks=[task_prog])
        prog_result = crew_prog.kickoff()
        prog_text = str(prog_result).strip()

        if prog_text.startswith("```"):
            lines = prog_text.splitlines()
            start_idx = 0
            end_idx = len(lines)
            for i, ln in enumerate(lines):
                if ln.strip().startswith("```json") or ln.strip() == "```":
                    start_idx = i + 1
                    break
            for j in range(start_idx, len(lines)):
                if lines[j].strip() == "```":
                    end_idx = j
                    break
            prog_text = "\n".join(lines[start_idx:end_idx]).strip()

        progress_system = json.loads(prog_text)
    except Exception as e:
        app.logger.error(f"[Progress Agent] Error: {e}")
        progress_system = {"error": str(e)}

    # Compose final plan
    complete_study_plan = {
        "created_at": datetime.now().isoformat(),
        "duration_days": study_duration_days,
        "syllabus_analysis": syllabus_analysis,
        "learning_analysis": learning_analysis,
        "schedule": schedule,
        "resources": resources,
        "progress_tracking": progress_system
    }

    return complete_study_plan


def generate_study_plan_pdf(study_plan):
    """
    Generate a comprehensive PDF report of the study plan
    (same as your previous implementation, left unchanged)
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", size=16)
    pdf.cell(200, 15, txt="Personalized Study Plan", ln=True, align='C')

    pdf.set_font("Arial", size=10)
    pdf.cell(200, 5, txt=f"Created: {study_plan.get('created_at', 'N/A')}", ln=True)
    pdf.cell(200, 5, txt=f"Duration: {study_plan.get('duration_days', 'N/A')} days", ln=True)
    pdf.ln(10)

    # Syllabus Analysis Section
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(200, 10, txt="1. Syllabus Analysis", ln=True)
    pdf.set_font("Arial", size=10)

    syllabus = study_plan.get('syllabus_analysis', {})
    if isinstance(syllabus, dict) and 'subjects' in syllabus:
        for subject in syllabus.get('subjects', []):
            pdf.cell(200, 8, txt=f"• {subject.get('name', 'Unknown')}", ln=True)
            for chapter in subject.get('chapters', [])[:3]:
                pdf.cell(200, 6, txt=f"  - {chapter.get('name', 'Unknown')} ({chapter.get('estimated_hours', 0)}h)", ln=True)
    pdf.ln(5)

    # Learning Analysis Section
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(200, 10, txt="2. Learning Style & Preferences", ln=True)
    pdf.set_font("Arial", size=10)

    learning = study_plan.get('learning_analysis', {})
    if isinstance(learning, dict) and 'error' not in learning:
        pdf.cell(200, 6, txt=f"Primary Style: {learning.get('primary_learning_style', 'N/A')}", ln=True)
        if learning.get('recommended_study_methods'):
            pdf.cell(200, 6, txt="Recommended Methods:", ln=True)
            for method in learning.get('recommended_study_methods', [])[:3]:
                pdf.cell(200, 5, txt=f"  • {method}", ln=True)
    pdf.ln(5)

    # Schedule Section
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(200, 10, txt="3. Study Schedule (Sample Days)", ln=True)
    pdf.set_font("Arial", size=9)

    schedule = study_plan.get('schedule', {})
    if isinstance(schedule, dict) and 'schedule' in schedule:
        for day in schedule.get('schedule', [])[:5]:
            pdf.cell(200, 6, txt=f"Day {day.get('day', 'N/A')}: {day.get('date', 'N/A')}", ln=True)
            for session in day.get('sessions', [])[:2]:
                pdf.cell(200, 5, txt=f"  • {session.get('time', 'N/A')}: {session.get('topic', 'N/A')}", ln=True)
    pdf.ln(5)

    # Resources Section
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(200, 10, txt="4. Recommended Resources", ln=True)
    pdf.set_font("Arial", size=9)

    resources = study_plan.get('resources', {})
    if isinstance(resources, dict) and 'resource_recommendations' in resources:
        for rec in resources.get('resource_recommendations', [])[:3]:
            pdf.cell(200, 6, txt=f"• {rec.get('topic', 'Unknown')}", ln=True)
            for res in rec.get('resources', [])[:2]:
                pdf.cell(200, 5, txt=f"  - {res.get('name', 'Unknown')} ({res.get('type', 'Unknown')})", ln=True)
    pdf.ln(5)

    # Progress Tracking Section
    pdf.set_font("Arial", "B", size=12)
    pdf.cell(200, 10, txt="5. Progress Tracking & Checkpoints", ln=True)
    pdf.set_font("Arial", size=9)

    progress = study_plan.get('progress_tracking', {})
    if isinstance(progress, dict) and 'checkpoint_schedule' in progress:
        for checkpoint in progress.get('checkpoint_schedule', [])[:4]:
            pdf.cell(200, 6, txt=f"• Day {checkpoint.get('day', 'N/A')}: {checkpoint.get('checkpoint', 'Unknown')}", ln=True)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes


# ---------------------------------------------------------------------
# FLASK ROUTES (unchanged behavior)
# ---------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    try:
        # Validate file
        if 'file' not in request.files:
            return jsonify({'error': 'No PDF file provided. Please upload a syllabus PDF.'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected. Please choose a PDF file.'}), 400

        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400

        # Validate other fields
        learning_preferences = request.form.get('learning_preferences', '')
        study_duration_days = int(request.form.get('study_duration_days', 30))
        if not learning_preferences:
            return jsonify({'error': 'Learning preferences are required'}), 400

        # Parse PDF (this is memory light)
        try:
            syllabus_text, page_count = parse_pdf_file(file)
        except ValueError as ve:
            return jsonify({'error': f'PDF parsing error: {str(ve)}'}), 400
        except Exception as e:
            return jsonify({'error': f'Failed to parse PDF: {str(e)}'}), 500

        # Create study plan
        study_plan = create_study_plan(syllabus_text, learning_preferences, study_duration_days)

        # If create_study_plan returned an error field, propagate as 500
        if isinstance(study_plan, dict) and study_plan.get('error'):
            return jsonify({'error': study_plan.get('error')}), 500

        plan_id = f"plan_{int(datetime.now().timestamp())}"
        study_plans[plan_id] = study_plan

        return jsonify({
            'success': True,
            'plan_id': plan_id,
            'message': 'Study plan generated successfully from PDF',
            'pdf_info': {
                'filename': file.filename,
                'pages': page_count
            },
            'summary': {
                'created_at': study_plan.get('created_at'),
                'duration_days': study_plan.get('duration_days'),
                'total_estimated_hours': study_plan.get('syllabus_analysis', {}).get('total_estimated_hours', 'N/A'),
                'primary_learning_style': study_plan.get('learning_analysis', {}).get('primary_learning_style', 'N/A')
            }
        }), 200

    except Exception as e:
        app.logger.exception("Unhandled error in /api/generate-plan")
        return jsonify({'error': f'Failed to generate study plan: {str(e)}'}), 500


@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    try:
        if plan_id not in study_plans:
            return jsonify({'error': 'Plan not found'}), 404
        return jsonify({'success': True, 'plan': study_plans[plan_id]}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plan/<plan_id>/pdf', methods=['GET'])
def download_plan_pdf(plan_id):
    try:
        if plan_id not in study_plans:
            return jsonify({'error': 'Plan not found'}), 404
        pdf_bytes = generate_study_plan_pdf(study_plans[plan_id])
        return pdf_bytes, 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename=study_plan_{plan_id}.pdf'
        }
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/plans', methods=['GET'])
def list_plans():
    try:
        plans_summary = []
        for plan_id, plan in study_plans.items():
            plans_summary.append({
                'plan_id': plan_id,
                'created_at': plan.get('created_at'),
                'duration_days': plan.get('duration_days'),
                'primary_learning_style': plan.get('learning_analysis', {}).get('primary_learning_style', 'N/A')
            })
        return jsonify({'success': True, 'plans': plans_summary, 'total_plans': len(plans_summary)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # Return whether agents are initialized (for debugging)
        status = {
            'status': 'healthy',
            'service': 'Study Plan Generator',
            'agents_initialized': _agents_initialized,
            'llm_configured': _llm_instance is not None,
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
