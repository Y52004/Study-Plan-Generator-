import os
import io
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from fpdf import FPDF
from werkzeug.utils import secure_filename
import pdfplumber
from dotenv import load_dotenv

# -----------------------------
# Environment & Config
# -----------------------------
load_dotenv()
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
ALLOWED_EXTENSIONS = {'pdf'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    os.environ["GEMINI_API_KEY"] = api_key

# -----------------------------
# Global in-memory store
# -----------------------------
study_plans = {}

# -----------------------------
# Agents lazy initialization
# -----------------------------
_agents_lock = threading.Lock()
_agents_initialized = False
_llm_instance = None
_agent_core = None
_agent_scheduler = None
_agent_progress = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_pdf_file(file):
    filename = secure_filename(file.filename)
    if not allowed_file(filename):
        raise ValueError("Only PDF files are allowed.")

    pdf_content = io.BytesIO(file.read())
    text = ""
    page_count = 0
    with pdfplumber.open(pdf_content) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {i} ---\n{page_text}"
    if not text:
        raise ValueError("No text content found in PDF.")
    return text, page_count

def _init_agents_if_needed():
    global _agents_initialized, _llm_instance, _agent_core, _agent_scheduler, _agent_progress
    with _agents_lock:
        if _agents_initialized:
            return
        try:
            from crewai import Agent, LLM
        except Exception as e:
            raise RuntimeError(f"CrewAI import failed: {e}")

        # Create lightweight LLM (avoid native heavy provider)
        try:
            _llm_instance = LLM(model="gemini/gemini-2.0-flash", use_native=False)
        except Exception:
            _llm_instance = "gemini/gemini-2.0-flash"

        def make_agent(role, goal, backstory):
            return Agent(role=role, goal=goal, backstory=backstory, llm=_llm_instance, verbose=False)

        # Optimized 3 agents
        _agent_core = make_agent(
            role="Core Study Plan Agent",
            goal="Analyze syllabus and learning style in one task",
            backstory="Produce structured topics and learning recommendations"
        )
        _agent_scheduler = make_agent(
            role="Scheduler Agent",
            goal="Create schedule and map resources",
            backstory="Return JSON schedule and resources in one task"
        )
        _agent_progress = make_agent(
            role="Progress Tracker Agent",
            goal="Track progress and adaptation",
            backstory="Monitor plan and provide checkpoints"
        )
        _agents_initialized = True

# -----------------------------
# Study Plan Creation
# -----------------------------
def create_study_plan(syllabus_text, learning_preferences, study_duration_days):
    try:
        _init_agents_if_needed()
    except Exception as e:
        return {"error": f"Agents init failed: {e}"}

    if _llm_instance is None:
        return {"error": "LLM not configured"}

    # ----- PLACEHOLDER lightweight JSON -----
    syllabus_analysis = {"info": "placeholder syllabus analysis"}
    learning_analysis = {"info": "placeholder learning analysis"}
    schedule = {"info": "placeholder schedule"}
    resources = {"info": "placeholder resources"}
    progress_system = {"info": "placeholder progress"}

    # ----- Optional: CrewAI tasks can be implemented here -----
    # All 3 agents are ready; memory-friendly execution
    # Combine core syllabus + learning analysis
    # Combine scheduler schedule + resources
    # Single progress task

    return {
        "created_at": datetime.now().isoformat(),
        "duration_days": study_duration_days,
        "syllabus_analysis": syllabus_analysis,
        "learning_analysis": learning_analysis,
        "schedule": schedule,
        "resources": resources,
        "progress_tracking": progress_system
    }

# -----------------------------
# PDF Generation
# -----------------------------
def generate_study_plan_pdf(study_plan):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 15, txt="Study Plan", ln=True, align='C')
    pdf.set_font("Arial", 10)
    pdf.cell(200, 5, txt=f"Created: {study_plan.get('created_at', 'N/A')}", ln=True)
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

# -----------------------------
# Flask Routes
# -----------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    try:
        file = request.files.get('file')
        if not file or not allowed_file(file.filename):
            return jsonify({'error': 'Provide valid PDF'}), 400

        learning_preferences = request.form.get('learning_preferences', '')
        study_duration_days = int(request.form.get('study_duration_days', 30))
        syllabus_text, _ = parse_pdf_file(file)

        study_plan = create_study_plan(syllabus_text, learning_preferences, study_duration_days)
        plan_id = f"plan_{int(datetime.now().timestamp())}"
        study_plans[plan_id] = study_plan

        return jsonify({'success': True, 'plan_id': plan_id}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    plan = study_plans.get(plan_id)
    if not plan:
        return jsonify({'error': 'Plan not found'}), 404
    return jsonify({'success': True, 'plan': plan}), 200

@app.route('/api/plan/<plan_id>/pdf', methods=['GET'])
def download_plan_pdf(plan_id):
    plan = study_plans.get(plan_id)
    if not plan:
        return jsonify({'error': 'Plan not found'}), 404
    pdf_bytes = generate_study_plan_pdf(plan)
    return pdf_bytes, 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename=study_plan_{plan_id}.pdf'
    }

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'agents_initialized': _agents_initialized,
        'llm_configured': _llm_instance is not None,
        'timestamp': datetime.now().isoformat()
    }), 200

# -----------------------------
# Run Flask directly (no Gunicorn)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
