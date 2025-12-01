# Study Plan Generator

AI-powered personalized study plan generation using 5 specialized CrewAI agents and Google Gemini.

## 🎯 Features

- **PDF Upload**: Upload your syllabus PDF for analysis
- **5 AI Agents**: Specialized agents for different aspects of study planning
  - 🔍 Syllabus Analyzer: Extracts and analyzes PDF content
  - 🎨 Learning Style Assessor: Profiles your learning preferences
  - 📅 Schedule Architect: Creates day-by-day study plans
  - 📚 Resource Recommender: Suggests study materials
  - 📈 Progress Tracker: Sets up monitoring systems
- **Personalized Plans**: Customized schedules based on your learning style
- **PDF Export**: Download your study plan as PDF

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Gemini API Key (free from [makersuite.google.com](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/CNNproj.git
cd CNNproj
```

2. **Create virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_google_api_key_here
FLASK_ENV=development
FLASK_DEBUG=True
```

5. **Run the application**
```bash
python app.py
```

6. **Open in browser**
Navigate to `http://localhost:5000`

## 📁 Project Structure

```
CNNproj/
├── app.py                    # Main Flask application & 5 CrewAI agents
├── requirements.txt          # Python dependencies
├── .env.example             # Example environment variables
├── .gitignore               # Git ignore rules
├── README.md                # This file
├── templates/
│   └── index.html           # Web UI
├── static/
│   ├── app.js               # Frontend logic
│   └── style.css            # Styling (dark theme)
└── uploads/                 # Uploaded PDFs (temporary)
```

## 🔧 Tech Stack

- **Backend**: Flask 2.3.3
- **AI/Agents**: CrewAI 1.6.1
- **LLM**: Google Gemini 2.0 Flash
- **PDF Processing**: pdfplumber 0.10.3
- **PDF Generation**: fpdf2 2.7.0
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## 📋 API Endpoints

### POST `/api/generate-plan`
Generate a study plan from PDF upload

**Request:**
- `file`: PDF file (multipart/form-data)
- `learning_preferences`: Learning style details
- `study_duration_days`: Number of days for plan

**Response:**
```json
{
  "plan_id": "unique-id",
  "summary": {
    "duration_days": 30,
    "total_estimated_hours": 120,
    "primary_learning_style": "visual"
  }
}
```

### GET `/api/plan/<plan_id>`
Retrieve generated study plan details

### GET `/api/plan/<plan_id>/pdf`
Download study plan as PDF

### GET `/api/plans`
List all generated plans

### GET `/api/health`
Health check endpoint

## 🎓 How It Works

1. **Upload PDF**: Submit your syllabus PDF
2. **Specify Preferences**: Choose learning style, study hours, pace
3. **Set Duration**: Define total study period
4. **Agent Processing**: 5 agents collaborate to create plan
   - Agent 1 analyzes the syllabus
   - Agent 2 assesses your learning style
   - Agent 3 creates the schedule
   - Agent 4 recommends resources
   - Agent 5 sets up progress tracking
5. **View & Download**: See results and download as PDF

## 📊 Study Plan Includes

- **Syllabus Analysis**: Topics, chapters, estimated study time
- **Learning Approach**: Customized methods based on your style
- **Day-by-Day Schedule**: Detailed daily study plan
- **Resource Recommendations**: Suggested materials and tools
- **Progress Checkpoints**: Milestones and monitoring points

## 🛠️ Troubleshooting

### Installation Issues

**Issue**: `Failed building wheel for chroma-hnswlib`
**Solution**: Use `install-simple.bat` for stage-by-stage installation

**Issue**: `ResolutionImpossible` pip error
**Solution**: Try clearing pip cache: `pip cache purge`

### Runtime Issues

**Issue**: `GEMINI_API_KEY not found`
**Solution**: Ensure `.env` file exists with valid API key

**Issue**: PDF upload fails
**Solution**: Ensure PDF is text-based (not scanned image)

## 📝 Configuration

Edit `app.py` to customize:
- `MAX_FILE_SIZE`: Maximum PDF file size (50MB default)
- `ALLOWED_EXTENSIONS`: Allowed file types
- Agent configurations and LLM parameters

## 🔒 Security

- ✅ `.env` file is in `.gitignore` (API keys never committed)
- ✅ File upload validation
- ✅ Secure filename handling with `werkzeug.secure_filename`
- ✅ Session-based plan storage

## 📄 License

MIT License - feel free to use for personal or commercial projects

## 🤝 Contributing

Contributions welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## 📞 Support

For issues or questions:
1. Check the troubleshooting section
2. Review API documentation in app.py
3. Check GitHub Issues

## 🚀 Future Enhancements

- [ ] Database integration for plan persistence
- [ ] User authentication
- [ ] Multiple PDF support
- [ ] Plan sharing and collaboration
- [ ] Progress tracking dashboard
- [ ] Integration with popular learning platforms

---

**Built with ❤️ using CrewAI and Google Gemini**
