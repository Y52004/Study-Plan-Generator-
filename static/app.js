// Global variables
let currentPlanId = null;

// Ensure page scrolls to top on load/refresh
window.addEventListener("load", () => {
    window.scrollTo(0, 0);
});

// ============================================================================
// SCREEN NAVIGATION
// ============================================================================

// Show plan form
function showPlanForm() {
    document.getElementById("home-screen").classList.remove("active");
    document.getElementById("plan-form-screen").classList.add("active");
    window.scrollTo(0, 0);
}

// Back to home
function backToHome() {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById("home-screen").classList.add("active");
    window.scrollTo(0, 0);
}

// ============================================================================
// TOAST NOTIFICATIONS
// ============================================================================

function showToast(message, type = 'info', duration = 3000) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, duration);
}

// ============================================================================
// FILE INPUT HANDLING
// ============================================================================

// Handle PDF file selection
document.getElementById('syllabus-pdf').addEventListener('change', function(e) {
    const file = this.files[0];
    const preview = document.getElementById('file-preview');
    
    if (file) {
        const fileSize = (file.size / 1024 / 1024).toFixed(2);
        preview.textContent = `✓ ${file.name} (${fileSize} MB)`;
        preview.style.color = '#10b981';
    } else {
        preview.textContent = '';
    }
});

// ============================================================================
// STUDY PLAN FORM SUBMISSION
// ============================================================================

document.getElementById('study-plan-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Validate PDF file
    const pdfFile = document.getElementById('syllabus-pdf').files[0];
    if (!pdfFile) {
        showToast('Please select a PDF file', 'error');
        return;
    }
    
    if (pdfFile.type !== 'application/pdf') {
        showToast('Please upload a PDF file only', 'error');
        return;
    }
    
    // Get form data
    const formData = new FormData();
    formData.append('file', pdfFile);
    
    // Combine learning preferences
    const learningStyle = document.getElementById('learning-style').value;
    const studyHours = document.getElementById('study-hours').value;
    const learningPace = document.getElementById('learn-pace').value;
    const additionalPrefs = document.getElementById('additional-prefs').value;
    
    const learningPreferences = `Learning Style: ${learningStyle}. Study Hours: ${studyHours}. Pace: ${learningPace}. Additional: ${additionalPrefs}`;
    formData.append('learning_preferences', learningPreferences);
    
    const studyDuration = document.getElementById('study-duration').value;
    formData.append('study_duration_days', studyDuration);
    
    // Show loader
    document.getElementById('form-loader').style.display = 'block';
    document.getElementById('form-status').textContent = '';
    
    try {
        const response = await fetch('/api/generate-plan', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to generate study plan');
        }
        
        // Store plan ID
        currentPlanId = result.plan_id;
        
        // Show results
        document.getElementById('form-loader').style.display = 'none';
        displayPlanResults(result);
        
        showToast('✓ Study plan generated successfully!', 'success', 5000);
        
    } catch (error) {
        document.getElementById('form-loader').style.display = 'none';
        showToast(`Error: ${error.message}`, 'error', 5000);
        document.getElementById('form-status').textContent = `Error: ${error.message}`;
    }
});

// ============================================================================
// RESULTS DISPLAY
// ============================================================================

function displayPlanResults(result) {
    // Hide form, show results
    document.getElementById('plan-form-screen').classList.remove('active');
    document.getElementById('results-screen').classList.add('active');
    
    // Update summary
    document.getElementById('summary-plan-id').textContent = result.plan_id;
    document.getElementById('summary-duration').textContent = `${result.summary.duration_days} days`;
    document.getElementById('summary-hours').textContent = result.summary.total_estimated_hours;
    document.getElementById('summary-style').textContent = result.summary.primary_learning_style || 'Personalized';
    
    // Store full result for later
    window.currentPlanResult = result;
    
    window.scrollTo(0, 0);
}

function downloadPlan() {
    if (!currentPlanId) {
        showToast('No plan available for download', 'error');
        return;
    }
    
    // Show loading
    showToast('📥 Downloading your study plan PDF...', 'info');
    
    // Trigger download
    const downloadUrl = `/api/plan/${currentPlanId}/pdf`;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `study_plan_${currentPlanId}.pdf`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(a.href);
    document.body.removeChild(a);
    
    setTimeout(() => {
        showToast('✓ PDF downloaded successfully!', 'success');
    }, 1000);
}

function viewPlanDetails() {
    const detailsDiv = document.getElementById('plan-details');
    const contentDiv = document.getElementById('details-content');
    
    if (detailsDiv.style.display === 'none') {
        detailsDiv.style.display = 'block';
        loadPlanDetails();
    } else {
        detailsDiv.style.display = 'none';
    }
}

async function loadPlanDetails() {
    if (!currentPlanId) return;
    
    try {
        const response = await fetch(`/api/plan/${currentPlanId}`);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Failed to load plan details');
        }
        
        const plan = result.plan;
        let html = '';
        
        // Syllabus Analysis
        if (plan.syllabus_analysis && !plan.syllabus_analysis.error) {
            html += `
                <div class="detail-section">
                    <h4>📚 Syllabus Analysis</h4>
                    <p><strong>Total Estimated Hours:</strong> ${plan.syllabus_analysis.total_estimated_hours || 'N/A'}</p>
            `;
            
            if (plan.syllabus_analysis.subjects) {
                html += '<p><strong>Subjects:</strong></p><ul>';
                plan.syllabus_analysis.subjects.forEach(subject => {
                    html += `<li>${subject.name} (${subject.chapters?.length || 0} chapters)</li>`;
                });
                html += '</ul>';
            }
            html += '</div>';
        }
        
        // Learning Style Analysis
        if (plan.learning_analysis && !plan.learning_analysis.error) {
            html += `
                <div class="detail-section">
                    <h4>🎨 Learning Style</h4>
                    <p><strong>Primary Style:</strong> ${plan.learning_analysis.primary_learning_style || 'N/A'}</p>
            `;
            
            if (plan.learning_analysis.recommended_study_methods) {
                html += '<p><strong>Recommended Methods:</strong></p><ul>';
                plan.learning_analysis.recommended_study_methods.forEach(method => {
                    html += `<li>${method}</li>`;
                });
                html += '</ul>';
            }
            html += '</div>';
        }
        
        // Study Schedule
        if (plan.schedule && plan.schedule.schedule) {
            html += `
                <div class="detail-section">
                    <h4>📅 Study Schedule (First 5 Days)</h4>
            `;
            
            plan.schedule.schedule.slice(0, 5).forEach(day => {
                html += `<div style="margin-bottom: 15px;">
                    <strong>Day ${day.day}:</strong> ${day.date || 'N/A'}`;
                
                if (day.sessions) {
                    html += '<ul style="margin: 5px 0;">';
                    day.sessions.forEach(session => {
                        html += `<li>${session.time}: ${session.topic}</li>`;
                    });
                    html += '</ul>';
                }
                html += '</div>';
            });
            
            html += '</div>';
        }
        
        // Resources
        if (plan.resources && plan.resources.resource_recommendations) {
            html += `
                <div class="detail-section">
                    <h4>📚 Recommended Resources</h4>
            `;
            
            plan.resources.resource_recommendations.slice(0, 3).forEach(rec => {
                html += `<p><strong>${rec.topic}:</strong></p><ul>`;
                rec.resources?.forEach(res => {
                    html += `<li>${res.name} (${res.type})</li>`;
                });
                html += '</ul>';
            });
            
            html += '</div>';
        }
        
        // Progress Tracking
        if (plan.progress_tracking && plan.progress_tracking.checkpoint_schedule) {
            html += `
                <div class="detail-section">
                    <h4>📈 Progress Checkpoints</h4>
                    <ul>
            `;
            
            plan.progress_tracking.checkpoint_schedule.forEach(checkpoint => {
                html += `<li>Day ${checkpoint.day}: ${checkpoint.checkpoint}</li>`;
            });
            
            html += '</ul></div>';
        }
        
        document.getElementById('details-content').innerHTML = html;
        
    } catch (error) {
        showToast(`Error loading details: ${error.message}`, 'error');
        document.getElementById('details-content').innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Study Plan Generator initialized');
    console.log('5 CrewAI Agents ready:');
    console.log('  1. Syllabus Analyzer Agent (PDF Handler)');
    console.log('  2. Learning Style Assessor Agent');
    console.log('  3. Schedule Architect Agent');
    console.log('  4. Resource Recommender Agent');
    console.log('  5. Progress Tracker & Adaptation Agent');
});
