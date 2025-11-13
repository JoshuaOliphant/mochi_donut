# Mochi Donut Web Interface

This document describes the comprehensive web interface created for Mochi Donut using Jinja2 templates with HTMX for progressive enhancement.

## Architecture Overview

The web interface follows a component-based architecture with:

- **Base Template**: Responsive layout with dark mode support
- **Reusable Components**: Quality scores, progress bars, pagination, prompt cards
- **HTMX Integration**: Progressive enhancement for dynamic updates
- **Tailwind CSS**: Utility-first styling with custom theme
- **Accessibility**: ARIA labels, keyboard navigation, semantic HTML

## File Structure

```
src/app/web/
├── __init__.py
├── routes.py                          # FastAPI web routes
└── templates/
    ├── base.html                      # Base template with navigation
    ├── components/
    │   ├── alert.html                 # Flash message component
    │   ├── base_partial.html          # Partial template for HTMX
    │   ├── pagination.html            # Pagination with HTMX support
    │   ├── processing_status.html     # Real-time processing status
    │   ├── progress_bar.html          # Progress indicators and spinners
    │   ├── prompt_card.html           # Prompt display and editing
    │   ├── prompt_list.html           # List view for HTMX updates
    │   └── quality_score.html         # Quality score visualization
    └── pages/
        ├── analytics.html             # Analytics dashboard
        ├── index.html                 # Home page with content submission
        ├── review.html                # Prompt review interface
        └── settings.html              # Configuration page
```

## Key Features

### 1. Progressive Enhancement with HTMX

- **Dual Rendering**: All pages work without JavaScript, enhanced with HTMX
- **Dynamic Updates**: Form submissions, filtering, and actions without page reload
- **Real-time Processing**: Live updates during content processing
- **Infinite Scroll**: Optional pagination enhancement

### 2. Component System

#### Quality Score Component
```jinja2
{{ quality_score(score=0.85, size='normal', show_label=true) }}
```

- Circular progress indicator
- Color-coded quality levels
- Multiple sizes (small, normal, large)

#### Prompt Card Component
```jinja2
{{ prompt_card(prompt, show_actions=true, compact=false) }}
```

- Inline editing with double-click
- Status badges and quality indicators
- Approve/reject/edit actions
- Responsive design

#### Progress Bar Component
```jinja2
{{ progress_bar(value=75, max_value=100, label="Processing", color="primary") }}
```

- Multi-step processing visualization
- Loading spinners
- Customizable colors and sizes

### 3. Page Templates

#### Home Page (`/web/`)
- Content submission form (URL or file upload)
- Dashboard statistics
- Recent activity timeline
- Processing options

#### Review Page (`/web/review`)
- Filterable prompt list
- Bulk actions
- Quality sorting
- Pagination with HTMX

#### Analytics Page (`/web/analytics`)
- Key metrics dashboard
- Quality trends
- Processing volume charts
- Cost breakdown

#### Settings Page (`/web/settings`)
- API configuration
- Processing preferences
- System information
- Backup controls

## HTMX Integration Patterns

### Form Submissions
```html
<form hx-post="/web/content/process"
      hx-target="#processing-status"
      hx-swap="innerHTML"
      hx-indicator="#submit-spinner">
```

### Dynamic Filtering
```html
<select hx-get="/web/review"
        hx-target="#content-area"
        hx-push-url="true"
        hx-trigger="change">
```

### Inline Editing
```html
<div hx-get="/web/prompts/{{ prompt.id }}/edit/question"
     hx-trigger="dblclick"
     hx-target="this"
     hx-swap="outerHTML">
```

## Styling and Theming

### Tailwind CSS Configuration
- Custom primary color palette (orange theme)
- Dark mode support with class-based switching
- Responsive breakpoints
- Custom animations and transitions

### Design System
- **Colors**: Primary (orange), success (green), warning (yellow), error (red)
- **Typography**: Consistent font scales and weights
- **Spacing**: 8px grid system
- **Shadows**: Subtle layering with elevation

## Accessibility Features

- **Keyboard Navigation**: Full keyboard support for all interactions
- **Screen Readers**: ARIA labels and semantic HTML structure
- **Color Contrast**: WCAG AA compliant color combinations
- **Focus Management**: Visible focus indicators
- **Skip Links**: Skip to main content option

## Integration with FastAPI

### Web Routes (`src/app/web/routes.py`)
- **Dual Endpoints**: Support both full page and HTMX partial responses
- **Flash Messages**: Session-based user feedback
- **Error Handling**: Graceful error responses
- **Template Context**: Automatic HTMX detection

### Main Application Updates
Add to `src/app/main.py`:

```python
from src.app.web.routes import web_router

# Include router
app.include_router(web_router)

# Redirect root to web interface
@app.get("/")
async def root():
    return RedirectResponse(url="/web/")
```

## Usage Examples

### Creating a Quality Score Display
```jinja2
{% from "components/quality_score.html" import quality_score %}
{{ quality_score(prompt.quality_score, size='large', show_label=true) }}
```

### Processing Status with Real-time Updates
```jinja2
{% include "components/processing_status.html" %}
```

### Filterable Content List
```jinja2
{% from "components/pagination.html" import pagination %}
{{ pagination(page_obj, 'web.review', **filters) }}
```

## Development Guidelines

### Template Inheritance
- Extend `base.html` for full pages
- Use `components/base_partial.html` for HTMX responses
- Import macros with `{% from %}`

### HTMX Best Practices
- Always include fallback behavior for non-JS users
- Use semantic HTTP methods (GET for retrieval, POST for mutations)
- Implement proper loading indicators
- Handle errors gracefully

### Component Development
- Create reusable macros for common UI patterns
- Include accessibility attributes
- Support dark mode theming
- Provide configurable options

## Performance Considerations

- **Template Caching**: Jinja2 auto-reload disabled in production
- **Asset Optimization**: CDN delivery for Tailwind CSS and HTMX
- **Progressive Loading**: Lazy loading for large lists
- **Minimal JavaScript**: HTMX provides most interactivity

## Security Features

- **CSRF Protection**: Token validation for form submissions
- **XSS Prevention**: Automatic template escaping
- **Content Security Policy**: Restrictive CSP headers
- **Input Validation**: Server-side validation for all inputs

This web interface provides a modern, accessible, and performant user experience for the Mochi Donut application while maintaining progressive enhancement principles.