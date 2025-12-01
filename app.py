from flask import Flask, request, jsonify, render_template
import os
import io
import json
from datetime import datetime
from fpdf import FPDF
from dotenv import load_dotenv
import threading
from werkzeug.utils import secure_filename
import pdfplumber

# Load environment variables
load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key

# Flask setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# In-memory storage for plans
study_plans = {}

# Thread-safe lazy init
_agents_lock = threading.Lock()
_agents_initialized = False
_llm_instance = None
_agent_core = None
_agent_scheduler = None
_agent_progress = None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_pdf_file(file):
    """Extract text from PDF"""
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        raise ValueError("Only PDF files are allowed.")
    pdf_content = io.BytesIO(file.read())
    text = ""
    with pdfplumber.open(pdf_content) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {page_num} ---\n{page_text}"
    if not text:
        raise ValueError("No text found in PDF.")
    return text, len(pdf.pages)


def _init_agents_if_needed():
    """Lazy-load CrewAI LLM and agents"""
    global _agents_initialized, _llm_instance, _agent_core, _agent_scheduler, _agent_progress
    with _agents_lock:
        if _agents_initialized:
            return
        try:
            from crewai import Agent, Task, Crew, LLM
        except Exception as e:
            raise RuntimeError(f"CrewAI import failed: {e}")
        try:
            _llm_instance = LLM(model="gemini/gemini-2.0-flash", use_native=False)
        except Exception as e:
            _llm_instance = None
            app.logger.warning(f"LLM init failed: {e}")
        def make_agent(role, goal, backstory):
            try:
                return Agent(role=role, goal=goal, backstory=backstory, llm=_llm_instance, verbose=False)
            except Exception as e:
                raise RuntimeError(f"Agent creation failed: {e}")
        _agent_core = make_agent("Core Agent",
                                 "Analyze syllabus and learning style",
                                 "Extract topics, chapters, and resources")
        _agent_scheduler = make_agent("Scheduler Agent",
                                      "Generate daily study schedule",
                                      "Map topics to days and sessions")
        _agent_progress = make_agent("Progress Tracker",
                                     "Create checkpoints and adaptation strategies",
                                     "Monitor progress and suggest adaptations")
        _agents_initialized = True


def create_study_plan(syllabus_text, learning_preferences, study_duration_days):
    try:
        _init_agents_if_needed()
    except Exception as e:
        return {"error": f"Server misconfiguration: {e}"}
    if _llm_instance is None:
        return {"error": "LLM not initialized. Check GEMINI_API_KEY."}

    syllabus_analysis = {}
    learning_analysis = {}
    schedule = {}
    resources = {}
    progress_system = {}

    # Core Agent
    try:
        from crewai import Task, Crew
        core_task = Task(
            description=f"""
Analyze SYLLABUS and LEARNING_PREFERENCES.
Return JSON:
{{
"syllabus_analysis": {{}},
"learning_analysis": {{}}
}}
""",
            expected_output="JSON with syllabus_analysis and learning_analysis",
            agent=_agent_core
        )
        core_crew = Crew(agents=[_agent_core], tasks=[core_task])
        core_result = core_crew.kickoff()
        core_text = str(core_result).strip()
        if core_text.startswith("```"):
            lines = core_text.splitlines()
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
        app.logger.error(f"[Core Agent] Error: {e}")
        syllabus_analysis = {"error": str(e)}
        learning_analysis = {"error": str(e)}

    # Scheduler Agent
    try:
        from crewai import Task, Crew
        sched_task = Task(
            description=f"""
Input: syllabus_analysis and learning_analysis
Output: JSON with schedule and resource_map
""",
            expected_output="JSON schedule & resource_map",
            agent=_agent_scheduler
        )
        sched_crew = Crew(agents=[_agent_scheduler], tasks=[sched_task])
        sched_result = sched_crew.kickoff()
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

    # Progress Agent
    try:
        from crewai import Task, Crew
        prog_task = Task(
            description=f"""
Input: syllabus_summary and schedule_summary
Output: JSON with tracking_metrics, checkpoints, adaptation_strategies
""",
            expected_output="JSON progress tracking",
            agent=_agent_progress
        )
        prog_crew = Crew(agents=[_agent_progress], tasks=[prog_task])
        prog_result = prog_crew.kickoff()
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

    return {
        "created_at": datetime.now().isoformat(),
        "duration_days": study_duration_days,
        "syllabus_analysis": syllabus_analysis,
        "learning_analysis": learning_analysis,
        "schedule": schedule,
        "resources": resources,
        "progress_tracking": progress_system
    }


def generate_study_plan_pdf(study_plan):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 15, "Personalized Study Plan", ln=True, align='C')
    pdf.set_font("Arial", "", 10)
    pdf.cell(200, 5, f"Created: {study_plan.get('created_at','N/A')}", ln=True)
    pdf.cell(200, 5, f"Duration: {study_plan.get('duration_days','N/A')} days", ln=True)
    pdf.ln(10)

    # Syllabus
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "1. Syllabus Analysis", ln=True)
    pdf.set_font("Arial", "", 10)
    for subj in study_plan.get('syllabus_analysis', {}).get('subjects', []):
        pdf.cell(200, 8, f"• {subj.get('name','Unknown')}", ln=True)
        for ch in subj.get('chapters', [])[:3]:
            pdf.cell(200, 6, f"  - {ch.get('name','Unknown')} ({ch.get('estimated_hours',0)}h)", ln=True)
    pdf.ln(5)

    # Learning style
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "2. Learning Style & Preferences", ln=True)
    pdf.set_font("Arial", "", 10)
    learning = study_plan.get('learning_analysis', {})
    pdf.cell(200, 6, f"Primary Style: {learning.get('primary_learning_style','N/A')}", ln=True)
    pdf.ln(5)

    # Schedule
    pdf.set_font("Arial", "B", 12)
    pdf.cell(200, 10, "3. Study Schedule (Sample Days)", ln=True)
    pdf.set_font("Arial", "", 9)
    schedule = study_plan.get('schedule', {}).get('schedule', [])
    for day in schedule[:5]:
        pdf.cell(200, 6, f"Day {day.get('day','N/A')}: {day.get('date','N/A')}", ln=True)
    pdf.ln(5)

    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes


# -------------------- Flask Routes --------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    try:
        if 'file' not in request.files:
            return jsonify({'error':'No PDF file provided'}),400
        file = request.files['file']
        if file.filename=='':
            return jsonify({'error':'No file selected'}),400
        if not allowed_file(file.filename):
            return jsonify({'error':'Only PDF allowed'}),400

        learning_preferences = request.form.get('learning_preferences','')
        study_duration_days = int(request.form.get('study_duration_days',30))
        if not learning_preferences:
            return jsonify({'error':'Learning preferences required'}),400

        syllabus_text, page_count = parse_pdf_file(file)
        study_plan = create_study_plan(syllabus_text, learning_preferences, study_duration_days)

        if 'error' in study_plan:
            return jsonify({'error': study_plan['error']}),500

        plan_id = f"plan_{int(datetime.now().timestamp())}"
        study_plans[plan_id] = study_plan

        return jsonify({
            'success': True,
            'plan_id': plan_id,
            'pdf_info': {'filename': file.filename,'pages': page_count},
            'summary': {
                'created_at': study_plan.get('created_at'),
                'duration_days': study_plan.get('duration_days'),
                'total_estimated_hours': study_plan.get('syllabus_analysis', {}).get('total_estimated_hours','N/A'),
                'primary_learning_style': study_plan.get('learning_analysis', {}).get('primary_learning_style','N/A')
            }
        }),200

    except Exception as e:
        app.logger.exception("Error generating plan")
        return jsonify({'error': str(e)}),500


@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    plan = study_plans.get(plan_id)
    if not plan:
        return jsonify({'error':'Plan not found'}),404
    return jsonify({'success': True, 'plan': plan}),200


@app.route('/api/plan/<plan_id>/pdf', methods=['GET'])
def download_plan_pdf(plan_id):
    plan = study_plans.get(plan_id)
    if not plan:
        return jsonify({'error':'Plan not found'}),404
    pdf_bytes = generate_study_plan_pdf(plan)
    return pdf_bytes,200,{
        'Content-Type':'application/pdf',
        'Content-Disposition': f'attachment; filename=study_plan_{plan_id}.pdf'
    }


@app.route('/api/plans', methods=['GET'])
def list_plans():
    plans_summary = []
    for pid, p in study_plans.items():
        plans_summary.append({
            'plan_id': pid,
            'created_at': p.get('created_at'),
            'duration_days': p.get('duration_days'),
            'primary_learning_style': p.get('learning_analysis', {}).get('primary_learning_style','N/A')
        })
    return jsonify({'success': True, 'plans': plans_summary, 'total_plans': len(plans_summary)}),200


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status':'healthy',
        'service':'Study Plan Generator',
        'agents_initialized': _agents_initialized,
        'llm_configured': _llm_instance is not None,
        'timestamp': datetime.now().isoformat()
    }),200


if __name__ == '__main__':
    # For local dev only; on Render use Gunicorn
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT",5000)))
