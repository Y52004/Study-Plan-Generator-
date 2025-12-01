from flask import Flask, request, jsonify, render_template
import json
import os
from datetime import datetime, timedelta
from fpdf import FPDF
from dotenv import load_dotenv
import io
import pdfplumber
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Get API key from environment variable
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY environment variable is not set!")
    print("Please set it using: $env:GEMINI_API_KEY='your-api-key-here' (PowerShell)")
    exit(1)

# Set environment variable for litellm
os.environ["GEMINI_API_KEY"] = api_key

# Import litellm for Gemini access
import litellm
litellm.set_verbose = False

# Import CrewAI
from crewai import Agent, Task, Crew

# Store study plans in memory
study_plans = {}

# Initialize LLM
llm = "gemini/gemini-2.0-flash"
print("Initializing LLM:", llm)

# ============================================================================
# AGENT 1: SYLLABUS ANALYZER AGENT
# ============================================================================
print("Creating Syllabus Analyzer Agent...")
syllabus_analyzer = Agent(
    role="Syllabus Analyzer",
    goal="Break down educational syllabus into organized topics with accurate time estimates for each topic",
    backstory="You are an expert curriculum analyst with years of experience in educational planning. You excel at identifying key topics, understanding learning dependencies, and estimating realistic time requirements for mastering each concept.",
    llm=llm,
    verbose=True
)
print("Syllabus Analyzer Agent created.")

# ============================================================================
# AGENT 2: LEARNING STYLE ASSESSOR AGENT
# ============================================================================
print("Creating Learning Style Assessor Agent...")
learning_style_assessor = Agent(
    role="Learning Style Assessor",
    goal="Analyze user's learning preferences, strengths, and challenges to create a personalized learning approach",
    backstory="You are a learning psychology expert who understands different learning styles (visual, auditory, kinesthetic, reading/writing). You adapt study strategies based on individual preferences and learning patterns to maximize comprehension and retention.",
    llm=llm,
    verbose=True
)
print("Learning Style Assessor Agent created.")

# ============================================================================
# AGENT 3: SCHEDULE ARCHITECT AGENT
# ============================================================================
print("Creating Schedule Architect Agent...")
schedule_architect = Agent(
    role="Schedule Architect",
    goal="Create detailed, day-by-day study schedules that balance learning objectives with realistic time management",
    backstory="You are a master scheduler and time management expert. You create practical, achievable study schedules that account for breaks, review sessions, and real-world constraints while optimizing learning outcomes.",
    llm=llm,
    verbose=True
)
print("Schedule Architect Agent created.")

# ============================================================================
# AGENT 4: RESOURCE RECOMMENDER AGENT
# ============================================================================
print("Creating Resource Recommender Agent...")
resource_recommender = Agent(
    role="Resource Recommender",
    goal="Suggest and recommend the most effective study materials, tools, and resources tailored to specific topics and learning styles",
    backstory="You are a research specialist with deep knowledge of educational resources, textbooks, online platforms, videos, and tools. You match resources to specific topics and learning preferences to enhance the study experience.",
    llm=llm,
    verbose=True
)
print("Resource Recommender Agent created.")

# ============================================================================
# AGENT 5: PROGRESS TRACKER & ADAPTATION AGENT
# ============================================================================
print("Creating Progress Tracker & Adaptation Agent...")
progress_tracker = Agent(
    role="Progress Tracker & Adaptation Specialist",
    goal="Create monitoring systems, track learning progress, and adapt study plans based on performance and feedback",
    backstory="You are an adaptive learning system expert who monitors student progress, identifies knowledge gaps, and recommends plan adjustments. You use data-driven insights to optimize study effectiveness and ensure continuous improvement.",
    llm=llm,
    verbose=True
)
print("Progress Tracker & Adaptation Agent created.")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file has allowed extension (PDF only)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_pdf_file(file):
    """
    Extract text content from PDF file
    This function is called by Agent 1 to read and process the PDF
    """
    print("\n[PDF Parser] Starting PDF file parsing...")
    try:
        filename = secure_filename(file.filename)
        print(f"[PDF Parser] Processing file: {filename}")
        
        # Check if file is PDF
        if not allowed_file(filename):
            print(f"[PDF Parser] ERROR: Invalid file type. Only PDF files are allowed.")
            raise ValueError("Invalid file type. Only PDF files are allowed. Please upload a PDF file.")
        
        # Read PDF content
        print("[PDF Parser] Reading PDF content...")
        pdf_content = io.BytesIO(file.read())
        
        extracted_text = ""
        page_count = 0
        
        # Extract text from all pages
        with pdfplumber.open(pdf_content) as pdf:
            page_count = len(pdf.pages)
            print(f"[PDF Parser] Found {page_count} pages in PDF")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    extracted_text += f"\n--- Page {page_num} ---\n{text}"
                    print(f"[PDF Parser] Extracted text from page {page_num}")
        
        if not extracted_text:
            print("[PDF Parser] ERROR: No text could be extracted from PDF")
            raise ValueError("No text content found in the PDF. Please provide a valid text-based PDF.")
        
        print(f"[PDF Parser] Successfully extracted {len(extracted_text)} characters from {page_count} pages")
        return extracted_text, page_count
        
    except Exception as e:
        print(f"[PDF Parser] ERROR: Failed to parse PDF - {str(e)}")
        raise


def create_study_plan(syllabus_text, learning_preferences, study_duration_days):
    """
    Main function to orchestrate the crew of agents to create a comprehensive study plan
    
    Args:
        syllabus_text: Text extracted from PDF by Agent 1
        learning_preferences: User's learning style preferences
        study_duration_days: Number of days for the study plan
    
    Agent 1 (Syllabus Analyzer) is responsible for:
    - Reading and processing the PDF content
    - Breaking down syllabus into organized topics
    - Identifying learning dependencies
    - Estimating time requirements for each topic
    """
    print("=" * 80)
    print("STARTING STUDY PLAN GENERATION WITH PDF INPUT")
    print("=" * 80)
    print("STARTING STUDY PLAN GENERATION")
    print("=" * 80)
    
    try:
        # STEP 1: Analyze Syllabus (Agent 1 handles PDF content)
        print("\n[STEP 1] [AGENT 1: Syllabus Analyzer] Analyzing PDF-extracted syllabus...")
        print("[STEP 1] Breaking down syllabus into organized topics with time estimates...")
        
        syllabus_task = Task(
            description=f"""You are analyzing a syllabus extracted from a PDF document. Your task is to break down this educational syllabus into organized topics with accurate time estimates.

SYLLABUS CONTENT FROM PDF:
{syllabus_text}

Analyze this syllabus carefully and return your analysis as a JSON object with this structure (ONLY JSON, no other text):
{{
    "pdf_analysis": {{
        "document_type": "PDF Syllabus",
        "content_quality": "assessment of content clarity"
    }},
    "subjects": [
        {{
            "name": "Subject/Module Name",
            "chapters": [
                {{"name": "Chapter Name", "estimated_hours": 5, "difficulty": "medium", "key_concepts": ["concept1", "concept2"]}}
            ]
        }}
    ],
    "total_estimated_hours": 100,
    "prerequisites": ["prerequisite1", "prerequisite2"],
    "learning_path_summary": "Brief summary of recommended learning path"
}}""",
            expected_output="JSON analysis of PDF syllabus with organized topics and time estimates",
            agent=syllabus_analyzer
        )
        
        syllabus_crew = Crew(agents=[syllabus_analyzer], tasks=[syllabus_task])
        syllabus_result = syllabus_crew.kickoff()
        syllabus_analysis_text = str(syllabus_result).strip()
        
        # Clean JSON response
        if syllabus_analysis_text.startswith('```'):
            lines = syllabus_analysis_text.split('\n')
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('```json') or line.strip() == '```':
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                syllabus_analysis_text = '\n'.join(lines[start_idx:end_idx]).strip()
        
        syllabus_analysis = json.loads(syllabus_analysis_text)
        print("✓ [AGENT 1] Syllabus analysis completed from PDF")
        print(f"  Total estimated hours: {syllabus_analysis.get('total_estimated_hours', 'N/A')}")
        if 'subjects' in syllabus_analysis:
            print(f"  Subjects identified: {len(syllabus_analysis.get('subjects', []))}")
        
    except Exception as e:
        print(f"✗ [AGENT 1] Error in syllabus analysis: {e}")
        syllabus_analysis = {"error": str(e)}
    
    try:
        # STEP 2: Assess Learning Style
        print("\n[STEP 2] Assessing learning style with Learning Style Assessor Agent...")
        learning_task = Task(
            description=f"""Based on the student's learning preferences provided, analyze and create a personalized learning approach.

Learning Preferences:
{learning_preferences}

Return your assessment as a JSON object with this structure (ONLY JSON, no other text):
{{
    "primary_learning_style": "visual|auditory|kinesthetic|reading-writing",
    "secondary_learning_styles": ["style1", "style2"],
    "strengths": ["strength1", "strength2"],
    "challenges": ["challenge1", "challenge2"],
    "recommended_study_methods": ["method1", "method2", "method3"],
    "personalized_tips": "Specific tips for this learner"
}}""",
            expected_output="JSON assessment of learning style and personalized approach",
            agent=learning_style_assessor
        )
        
        learning_crew = Crew(agents=[learning_style_assessor], tasks=[learning_task])
        learning_result = learning_crew.kickoff()
        learning_analysis_text = str(learning_result).strip()
        
        # Clean JSON response
        if learning_analysis_text.startswith('```'):
            lines = learning_analysis_text.split('\n')
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('```json') or line.strip() == '```':
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                learning_analysis_text = '\n'.join(lines[start_idx:end_idx]).strip()
        
        learning_analysis = json.loads(learning_analysis_text)
        print("✓ Learning style assessment completed")
        print(f"  Primary style: {learning_analysis.get('primary_learning_style', 'N/A')}")
        
    except Exception as e:
        print(f"✗ Error in learning style assessment: {e}")
        learning_analysis = {"error": str(e)}
    
    try:
        # STEP 3: Create Schedule
        print("\n[STEP 3] Creating study schedule with Schedule Architect Agent...")
        schedule_task = Task(
            description=f"""Create a detailed day-by-day study schedule based on:

Syllabus Topics:
{json.dumps(syllabus_analysis, indent=2)}

Learning Preferences:
{json.dumps(learning_analysis, indent=2)}

Study Duration: {study_duration_days} days
Study Hours per day: 4-6 hours

Return your schedule as a JSON object with this structure (ONLY JSON, no other text):
{{
    "schedule": [
        {{
            "day": 1,
            "date": "2025-12-01",
            "sessions": [
                {{
                    "session": 1,
                    "time": "09:00-11:00",
                    "topic": "Topic Name",
                    "subtopics": ["subtopic1", "subtopic2"],
                    "activities": ["activity1", "activity2"],
                    "break_after": 15
                }}
            ],
            "revision_topics": ["topic1"],
            "notes": "Any special notes for this day"
        }}
    ],
    "weekly_milestones": ["Milestone 1", "Milestone 2"]
}}""",
            expected_output="JSON detailed day-by-day study schedule",
            agent=schedule_architect
        )
        
        schedule_crew = Crew(agents=[schedule_architect], tasks=[schedule_task])
        schedule_result = schedule_crew.kickoff()
        schedule_text = str(schedule_result).strip()
        
        # Clean JSON response
        if schedule_text.startswith('```'):
            lines = schedule_text.split('\n')
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('```json') or line.strip() == '```':
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                schedule_text = '\n'.join(lines[start_idx:end_idx]).strip()
        
        schedule = json.loads(schedule_text)
        print("✓ Study schedule created")
        print(f"  Total days scheduled: {len(schedule.get('schedule', []))}")
        
    except Exception as e:
        print(f"✗ Error in schedule creation: {e}")
        schedule = {"error": str(e)}
    
    try:
        # STEP 4: Recommend Resources
        print("\n[STEP 4] Recommending resources with Resource Recommender Agent...")
        
        # Extract topics from syllabus analysis
        topics_str = json.dumps(syllabus_analysis, indent=2)[:1000]
        
        resource_task = Task(
            description=f"""Based on the topics and learning preferences, recommend study resources for each major topic.

Topics to Cover:
{topics_str}

Learning Style: {learning_analysis.get('primary_learning_style', 'visual')}

Return your recommendations as a JSON object with this structure (ONLY JSON, no other text):
{{
    "resource_recommendations": [
        {{
            "topic": "Topic Name",
            "resources": [
                {{
                    "type": "textbook|video|interactive|article|tool",
                    "name": "Resource Name",
                    "description": "Brief description",
                    "why_recommended": "Why this helps this learner"
                }}
            ]
        }}
    ],
    "study_tools": ["tool1", "tool2", "tool3"],
    "supplementary_resources": ["resource1", "resource2"]
}}""",
            expected_output="JSON recommendations for study resources",
            agent=resource_recommender
        )
        
        resource_crew = Crew(agents=[resource_recommender], tasks=[resource_task])
        resource_result = resource_crew.kickoff()
        resources_text = str(resource_result).strip()
        
        # Clean JSON response
        if resources_text.startswith('```'):
            lines = resources_text.split('\n')
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('```json') or line.strip() == '```':
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                resources_text = '\n'.join(lines[start_idx:end_idx]).strip()
        
        resources = json.loads(resources_text)
        print("✓ Resource recommendations completed")
        print(f"  Total resource recommendations: {len(resources.get('resource_recommendations', []))}")
        
    except Exception as e:
        print(f"✗ Error in resource recommendations: {e}")
        resources = {"error": str(e)}
    
    try:
        # STEP 5: Create Progress Tracking System
        print("\n[STEP 5] Creating progress tracking system with Progress Tracker Agent...")
        progress_task = Task(
            description=f"""Design a comprehensive progress tracking and adaptation system for this study plan.

Topics: {json.dumps(syllabus_analysis.get('subjects', [])[:2], indent=2)}
Schedule: {study_duration_days} days
Learning Style: {learning_analysis.get('primary_learning_style', 'visual')}

Return your tracking system as a JSON object with this structure (ONLY JSON, no other text):
{{
    "tracking_metrics": [
        {{
            "metric": "Metric Name",
            "how_to_measure": "How to measure this",
            "success_criteria": "What indicates success"
        }}
    ],
    "checkpoint_schedule": [
        {{
            "checkpoint": "Checkpoint Name",
            "day": 7,
            "assessment": "What to evaluate",
            "adaptation_triggers": ["trigger1", "trigger2"]
        }}
    ],
    "adaptation_strategies": [
        {{
            "scenario": "What happens if student is falling behind",
            "action": "Recommended action"
        }}
    ],
    "reflection_prompts": ["prompt1", "prompt2"]
}}""",
            expected_output="JSON progress tracking and adaptation system",
            agent=progress_tracker
        )
        
        progress_crew = Crew(agents=[progress_tracker], tasks=[progress_task])
        progress_result = progress_crew.kickoff()
        progress_text = str(progress_result).strip()
        
        # Clean JSON response
        if progress_text.startswith('```'):
            lines = progress_text.split('\n')
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip().startswith('```json') or line.strip() == '```':
                    if start_idx is None:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break
            if start_idx is not None and end_idx is not None:
                progress_text = '\n'.join(lines[start_idx:end_idx]).strip()
        
        progress_system = json.loads(progress_text)
        print("✓ Progress tracking system created")
        print(f"  Total checkpoints: {len(progress_system.get('checkpoint_schedule', []))}")
        
    except Exception as e:
        print(f"✗ Error in progress tracking: {e}")
        progress_system = {"error": str(e)}
    
    print("\n" + "=" * 80)
    print("STUDY PLAN GENERATION COMPLETED")
    print("=" * 80 + "\n")
    
    # Combine all results
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
    if 'subjects' in syllabus:
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
    if 'error' not in learning:
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
    if 'schedule' in schedule:
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
    if 'resource_recommendations' in resources:
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
    if 'checkpoint_schedule' in progress:
        for checkpoint in progress.get('checkpoint_schedule', [])[:4]:
            pdf.cell(200, 6, txt=f"• Day {checkpoint.get('day', 'N/A')}: {checkpoint.get('checkpoint', 'Unknown')}", ln=True)
    
    # Save to buffer
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes




# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    """
    Generate a comprehensive study plan based on PDF syllabus and learning preferences
    
    This endpoint:
    1. Accepts a PDF file upload containing the syllabus
    2. Parses the PDF using pdfplumber
    3. Sends extracted text to Agent 1 (Syllabus Analyzer)
    4. Agent 1 breaks down the syllabus into topics with time estimates
    5. Orchestrates all 5 agents to create a complete study plan
    
    Expected Request (multipart/form-data):
    - file: PDF file containing syllabus (required)
    - learning_preferences: Student's learning style info (required)
    - study_duration_days: Number of days for study plan (optional, default: 30)
    """
    print("\n[Generate Plan Route] Processing request...")
    try:
        # Check if PDF file is provided
        print("[Generate Plan Route] Checking for PDF file in request...")
        if 'file' not in request.files:
            print("[Generate Plan Route] ERROR: No file provided in request")
            return jsonify({'error': 'No PDF file provided. Please upload a syllabus PDF.'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            print("[Generate Plan Route] ERROR: No file selected")
            return jsonify({'error': 'No file selected. Please choose a PDF file.'}), 400
        
        # Validate file type
        if not allowed_file(file.filename):
            print(f"[Generate Plan Route] ERROR: Invalid file type - {file.filename}")
            return jsonify({'error': 'Invalid file type. Only PDF files are allowed.'}), 400
        
        print(f"[Generate Plan Route] PDF file received: {file.filename}")
        
        # Get learning preferences and study duration
        learning_preferences = request.form.get('learning_preferences', '')
        study_duration_days = int(request.form.get('study_duration_days', 30))
        
        if not learning_preferences:
            print("[Generate Plan Route] ERROR: Learning preferences not provided")
            return jsonify({'error': 'Learning preferences are required'}), 400
        
        print(f"[Generate Plan Route] Learning preferences: {learning_preferences[:50]}...")
        print(f"[Generate Plan Route] Study duration: {study_duration_days} days")
        
        # STEP 1: Agent 1 (Syllabus Analyzer) reads and parses the PDF
        print("\n[Generate Plan Route] [AGENT 1] Starting PDF parsing and analysis...")
        try:
            syllabus_text, page_count = parse_pdf_file(file)
            print(f"[Generate Plan Route] [AGENT 1] ✓ PDF parsing successful - {page_count} pages processed")
        except ValueError as ve:
            print(f"[Generate Plan Route] [AGENT 1] ✗ PDF parsing failed: {str(ve)}")
            return jsonify({'error': f'PDF parsing error: {str(ve)}'}), 400
        except Exception as e:
            print(f"[Generate Plan Route] [AGENT 1] ✗ Unexpected error during PDF parsing: {str(e)}")
            return jsonify({'error': f'Failed to parse PDF: {str(e)}'}), 500
        
        print(f"[Generate Plan Route] Extracted syllabus text: {len(syllabus_text)} characters")
        
        # STEP 2: Create comprehensive study plan with all 5 agents
        print("[Generate Plan Route] Creating comprehensive study plan with all agents...")
        study_plan = create_study_plan(syllabus_text, learning_preferences, study_duration_days)
        
        # Store the plan
        plan_id = f"plan_{int(datetime.now().timestamp())}"
        study_plans[plan_id] = study_plan
        
        print(f"[Generate Plan Route] ✓ Study plan generated successfully with ID: {plan_id}")
        
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
        print(f"[Generate Plan Route] ✗ Error in generate_plan: {str(e)}")
        return jsonify({'error': f'Failed to generate study plan: {str(e)}'}), 500


@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """
    Retrieve a generated study plan
    """
    print(f"Get plan route called for ID: {plan_id}")
    try:
        if plan_id not in study_plans:
            return jsonify({'error': 'Plan not found'}), 404
        
        plan = study_plans[plan_id]
        return jsonify({
            'success': True,
            'plan': plan
        }), 200
        
    except Exception as e:
        print(f"Error in get_plan: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/plan/<plan_id>/pdf', methods=['GET'])
def download_plan_pdf(plan_id):
    """
    Download study plan as PDF
    """
    print(f"Download PDF route called for plan ID: {plan_id}")
    try:
        if plan_id not in study_plans:
            return jsonify({'error': 'Plan not found'}), 404
        
        plan = study_plans[plan_id]
        pdf_bytes = generate_study_plan_pdf(plan)
        
        return pdf_bytes, 200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename=study_plan_{plan_id}.pdf'
        }
        
    except Exception as e:
        print(f"Error in download_plan_pdf: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/plans', methods=['GET'])
def list_plans():
    """
    List all generated study plans
    """
    print("List plans route called.")
    try:
        plans_summary = []
        for plan_id, plan in study_plans.items():
            plans_summary.append({
                'plan_id': plan_id,
                'created_at': plan.get('created_at'),
                'duration_days': plan.get('duration_days'),
                'primary_learning_style': plan.get('learning_analysis', {}).get('primary_learning_style', 'N/A')
            })
        
        return jsonify({
            'success': True,
            'plans': plans_summary,
            'total_plans': len(plans_summary)
        }), 200
        
    except Exception as e:
        print(f"Error in list_plans: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Study Plan Generator',
        'llm': llm,
        'timestamp': datetime.now().isoformat()
    }), 200



if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("STUDY PLAN GENERATOR - POWERED BY CREWAI")
    print("=" * 80)
    print("\n✓ All 5 CrewAI Agents initialized:")
    print("  1. Syllabus Analyzer Agent")
    print("  2. Learning Style Assessor Agent")
    print("  3. Schedule Architect Agent")
    print("  4. Resource Recommender Agent")
    print("  5. Progress Tracker & Adaptation Agent")
    print("\n✓ LLM: Gemini 2.0 Flash")
    print("✓ Ready to generate personalized study plans!")
    print("=" * 80 + "\n")
    
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
