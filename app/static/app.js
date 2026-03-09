/**
 * Observability Course Frontend
 * HTMX helpers and quiz interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize HTMX event listeners
    setupHTMXListeners();
    
    // Highlight code blocks on page load and after HTMX swaps
    highlightCode();
    
    // Initialize Mermaid diagrams
    if (typeof mermaid !== 'undefined') {
        mermaid.contentLoaded();
    }
});

/**
 * Set up HTMX event listeners for dynamic content
 */
function setupHTMXListeners() {
    // After HTMX swap, re-highlight code and render diagrams
    document.addEventListener('htmx:afterSwap', function() {
        highlightCode();
        if (typeof mermaid !== 'undefined') {
            mermaid.contentLoaded();
        }
    });
    
    // Optional: Add loading state indicator
    document.addEventListener('htmx:request', function(evt) {
        // You could add a loading spinner here
    });
    
    // Optional: Handle errors
    document.addEventListener('htmx:responseError', function(evt) {
        console.error('HTMX Error:', evt.detail);
        alert('An error occurred. Please try again.');
    });
}

/**
 * Highlight code blocks using Highlight.js
 */
function highlightCode() {
    if (typeof hljs === 'undefined') {
        return;
    }
    
    document.querySelectorAll('pre code').forEach(block => {
        hljs.highlightElement(block);
    });
}

/**
 * Quiz validation
 */
function validateQuiz(form) {
    const questions = form.querySelectorAll('.question-item');
    let allAnswered = true;
    
    questions.forEach(question => {
        const answered = question.querySelector('input[type="radio"]:checked');
        if (!answered) {
            allAnswered = false;
            question.style.borderColor = '#da3633';
        } else {
            question.style.borderColor = '';
        }
    });
    
    if (!allAnswered) {
        alert('Please answer all questions before submitting.');
        return false;
    }
    
    return true;
}

/**
 * Toggle lesson completion with optimistic UI update
 */
function toggleLessonCompletion(lessonId, moduleId, lessonSlug, isCompleted) {
    const form = event.target.closest('form');
    
    // Optimistic UI update
    const button = form.querySelector('button');
    const wasCompleted = isCompleted === '1';
    
    if (wasCompleted) {
        button.classList.remove('btn-success');
        button.classList.add('btn-outline');
        button.textContent = 'Mark Complete';
    } else {
        button.classList.add('btn-success');
        button.classList.remove('btn-outline');
        button.textContent = '✅ Completed';
    }
    
    return true;
}

/**
 * Format time in minutes to readable format
 */
function formatEstimatedTime(minutes) {
    if (minutes < 1) {
        return 'Less than a minute';
    } else if (minutes === 1) {
        return '1 minute';
    } else {
        return minutes + ' minutes';
    }
}

/**
 * Track progress analytics
 */
function trackEvent(eventName, eventData = {}) {
    // Send to analytics endpoint
    const payload = {
        event: eventName,
        data: eventData,
        timestamp: new Date().toISOString()
    };
    
    // Could integrate with tracking service here
    console.log('[Analytics]', eventName, eventData);
}

/**
 * Simple trace visualizer
 * Usage: <div data-trace="path/to/trace.json"></div>
 */
function initializeTraceVisualizers() {
    document.querySelectorAll('[data-trace]').forEach(elem => {
        const tracePath = elem.dataset.trace;
        loadAndRenderTrace(tracePath, elem);
    });
}

async function loadAndRenderTrace(path, container) {
    try {
        const response = await fetch(path);
        const trace = await response.json();
        renderTraceWaterfall(trace, container);
    } catch (error) {
        console.error('Failed to load trace:', error);
        container.innerHTML = '<p>Failed to load trace data</p>';
    }
}

function renderTraceWaterfall(trace, container) {
    // Simple trace visualization
    const html = `
        <div class="trace-viewer">
            <div class="trace-info">
                <p><strong>Trace ID:</strong> ${trace.trace_id || 'N/A'}</p>
                <p><strong>Duration:</strong> ${(trace.duration || 0).toFixed(2)}ms</p>
            </div>
            <div class="trace-spans">
                ${trace.spans?.map((span, idx) => `
                    <div class="span" style="margin-left: ${span.depth * 20}px;">
                        <span class="span-name">${span.name}</span>
                        <span class="span-duration">${span.duration.toFixed(2)}ms</span>
                    </div>
                `).join('') || '<p>No spans found</p>'}
            </div>
        </div>
    `;
    container.innerHTML = html;
}

// Export functions for external use
window.CourseApp = {
    validateQuiz,
    toggleLessonCompletion,
    formatEstimatedTime,
    trackEvent,
    initializeTraceVisualizers
};
