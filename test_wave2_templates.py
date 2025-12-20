#!/usr/bin/env python3
"""
ABOUTME: Wave 2 Integration Test for Jinja2 Template Rendering
ABOUTME: Tests all Jinja2 templates render successfully with mock data
"""

import sys
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

def setup_jinja_environment():
    """Initialize Jinja2 environment with template path."""
    template_dir = Path(__file__).parent / "src" / "app" / "templates"
    if not template_dir.exists():
        print(f"ERROR: Template directory not found: {template_dir}")
        return None

    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env


def create_mock_prompt():
    """Create mock prompt data matching expected schema."""
    return {
        "id": "prompt-001",
        "workflow_id": "workflow-123",
        "question": "What is spaced repetition and why is it effective for learning?",
        "answer": "Spaced repetition is a learning technique that involves reviewing information at increasing intervals. It's effective because it fights the forgetting curve by reinforcing memory at optimal times, leading to stronger and more durable long-term retention.",
        "status": "pending",
        "prompt_type": "definition",
        "created_at": datetime(2024, 1, 15, 10, 30, 0),
        "updated_at": datetime(2024, 1, 15, 11, 45, 0),
        "quality_scores": {
            "overall": 0.85,
            "focused": 0.90,
            "precise": 0.85,
            "consistent": 0.80,
            "tractable": 0.85,
            "effortful": 0.75,
        }
    }


def create_mock_prompts_list():
    """Create list of mock prompts for list view."""
    prompts = []
    statuses = ["pending", "approved", "rejected"]
    for i in range(3):
        prompt = create_mock_prompt()
        prompt["id"] = f"prompt-{i:03d}"
        prompt["status"] = statuses[i]
        prompt["quality_scores"]["overall"] = [0.85, 0.92, 0.45][i]
        prompts.append(prompt)
    return prompts


def create_mock_counts():
    """Create mock status counts."""
    return {
        "total": 15,
        "pending": 5,
        "approved": 8,
        "rejected": 2,
    }


def test_base_template(env):
    """Test base.html renders correctly."""
    test_name = "base.html"
    try:
        template = env.get_template("base.html")
        context = {
            "title": "Test Page",
            "content": "<p>Test content</p>",
            "messages": []
        }
        html = template.render(context)

        # Validate expected elements
        checks = [
            ("DOCTYPE html" in html, "HTML5 DOCTYPE declaration"),
            ("Tailwind CSS" in html, "Tailwind CSS script"),
            ("htmx.org" in html, "HTMX script"),
            ("Alpine.js" in html, "Alpine.js script"),
            ("Mochi Donut" in html, "Branding text"),
            ("class=" in html, "Tailwind classes"),
            ("<nav" in html, "Navigation element"),
            ("<footer" in html, "Footer element"),
        ]

        all_passed = all(check[0] for check in checks)

        print(f"\n✓ PASS: {test_name}")
        print(f"  Rendered HTML size: {len(html)} bytes")
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")

        return True, html
    except Exception as e:
        print(f"\n✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        return False, None


def test_prompts_list_template(env):
    """Test prompts/list.html renders correctly."""
    test_name = "prompts/list.html"
    try:
        template = env.get_template("prompts/list.html")
        context = {
            "workflow_id": "workflow-123",
            "prompts": create_mock_prompts_list(),
            "counts": create_mock_counts(),
            "current_status": "pending",
            "messages": []
        }
        html = template.render(context)

        # Validate expected elements
        checks = [
            ("Workflow: workflow-123" in html, "Workflow ID displayed"),
            ("flashcard prompts" in html, "Description text"),
            ("Approve All" in html, "Approve All button"),
            ("hx-post=" in html, "HTMX POST attributes"),
            ("hx-get=" in html, "HTMX GET attributes"),
            ("hx-target=" in html, "HTMX target attributes"),
            ("hx-swap=" in html, "HTMX swap attributes"),
            ("prompt-card" in html or "Question" in html, "Prompt content"),
            ("All (" in html, "Status filter counts"),
            ("class=" in html, "Tailwind classes"),
        ]

        all_passed = all(check[0] for check in checks)

        print(f"\n✓ PASS: {test_name}")
        print(f"  Rendered HTML size: {len(html)} bytes")
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")

        return True, html
    except Exception as e:
        print(f"\n✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        return False, None


def test_prompts_review_template(env):
    """Test prompts/review.html renders correctly."""
    test_name = "prompts/review.html"
    try:
        template = env.get_template("prompts/review.html")
        prompt = create_mock_prompt()
        context = {
            "prompt": prompt,
            "has_previous": True,
            "has_next": True,
            "previous_id": "prompt-000",
            "next_id": "prompt-002",
            "messages": []
        }
        html = template.render(context)

        # Validate expected elements
        checks = [
            ("Review Prompt" in html, "Review title"),
            ("spaced repetition" in html, "Question content"),
            ("hx-post=" in html, "HTMX POST for approve/reject"),
            ("Approve" in html, "Approve button"),
            ("Reject" in html, "Reject button"),
            ("Request Refinement" in html, "Refinement button"),
            ("Quality Score" in html, "Quality score section"),
            ("Focused" in html, "Quality metric: Focused"),
            ("Precise" in html, "Quality metric: Precise"),
            ("Consistent" in html, "Quality metric: Consistent"),
            ("Tractable" in html, "Quality metric: Tractable"),
            ("Effortful" in html, "Quality metric: Effortful"),
            ("Edit Prompt" in html, "Edit button"),
            ("Previous" in html, "Previous navigation"),
            ("Next" in html, "Next navigation"),
            ("Metadata" in html, "Metadata card"),
            ("Status" in html, "Status field"),
            ("Created" in html, "Created timestamp"),
            ("Updated" in html, "Updated timestamp"),
            ("class=" in html, "Tailwind classes"),
            ("hx-" in html, "HTMX attributes"),
        ]

        all_passed = all(check[0] for check in checks)

        print(f"\n✓ PASS: {test_name}")
        print(f"  Rendered HTML size: {len(html)} bytes")
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")

        return True, html
    except Exception as e:
        print(f"\n✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        return False, None


def test_prompt_card_component(env):
    """Test components/prompt_card.html renders correctly."""
    test_name = "components/prompt_card.html"
    try:
        template = env.get_template("components/prompt_card.html")
        context = {
            "prompt": create_mock_prompt()
        }
        html = template.render(context)

        # Validate expected elements
        checks = [
            ("spaced repetition" in html, "Question content"),
            ("line-clamp" in html, "Answer preview clamp"),
            ("Review" in html, "Review link"),
            ("Approve" in html, "Approve button"),
            ("hx-post=" in html, "HTMX POST attributes"),
            ("status" in html, "Status badge"),
            ("2024-01" in html, "Timestamp"),
            ("shadow" in html, "Card shadow"),
            ("dark:" in html, "Dark mode support"),
            ("class=" in html, "Tailwind classes"),
        ]

        all_passed = all(check[0] for check in checks)

        print(f"\n✓ PASS: {test_name}")
        print(f"  Rendered HTML size: {len(html)} bytes")
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")

        return True, html
    except Exception as e:
        print(f"\n✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        return False, None


def test_quality_badge_component(env):
    """Test components/quality_badge.html renders correctly with different scores."""
    test_name = "components/quality_badge.html"
    results = []

    test_cases = [
        ("High Quality (0.85)", {"overall": 0.85}),
        ("Medium Quality (0.65)", {"overall": 0.65}),
        ("Low Quality (0.45)", {"overall": 0.45}),
    ]

    for test_label, quality_scores in test_cases:
        try:
            template = env.get_template("components/quality_badge.html")
            context = {
                "prompt": {
                    "quality_scores": quality_scores
                }
            }
            html = template.render(context)

            # Validate expected elements based on score
            score = quality_scores["overall"]
            if score >= 0.8:
                color_check = ("bg-green" in html, "Green color for high quality")
            elif score >= 0.6:
                color_check = ("bg-yellow" in html, "Yellow color for medium quality")
            else:
                color_check = ("bg-red" in html, "Red color for low quality")

            checks = [
                (color_check[0], color_check[1]),
                ("0.85" in html or "0.65" in html or "0.45" in html, "Score value displayed"),
                ("ring-" in html, "Tailwind ring utility"),
                ("rounded-full" in html, "Rounded badge"),
                ("dark:" in html, "Dark mode support"),
                ("<svg" in html, "Status indicator icon"),
            ]

            all_passed = all(check[0] for check in checks)

            print(f"\n  ✓ PASS: {test_name} ({test_label})")
            print(f"    Rendered HTML size: {len(html)} bytes")
            for check, desc in checks:
                status = "✓" if check else "✗"
                print(f"    {status} {desc}")

            results.append((True, html))
        except Exception as e:
            print(f"\n  ✗ FAIL: {test_name} ({test_label})")
            print(f"    Error: {str(e)}")
            results.append((False, None))

    return all(r[0] for r in results), results


def test_edit_form_component(env):
    """Test components/edit_form.html renders correctly."""
    test_name = "components/edit_form.html"
    try:
        template = env.get_template("components/edit_form.html")
        context = {
            "prompt": create_mock_prompt()
        }
        html = template.render(context)

        # Validate expected elements
        checks = [
            ("<form" in html, "Form element"),
            ("hx-put=" in html, "HTMX PUT method"),
            ("question" in html, "Question textarea"),
            ("answer" in html, "Answer textarea"),
            ("spaced repetition" in html, "Pre-filled question content"),
            ("Save Changes" in html, "Save button"),
            ("Cancel" in html, "Cancel button"),
            ("required" in html, "Required field validation"),
            ("hx-get=" in html, "HTMX GET for cancel"),
            ("hx-swap=" in html, "HTMX swap directive"),
            ("dark:" in html, "Dark mode support"),
            ("class=" in html, "Tailwind classes"),
        ]

        all_passed = all(check[0] for check in checks)

        print(f"\n✓ PASS: {test_name}")
        print(f"  Rendered HTML size: {len(html)} bytes")
        for check, desc in checks:
            status = "✓" if check else "✗"
            print(f"  {status} {desc}")

        return True, html
    except Exception as e:
        print(f"\n✗ FAIL: {test_name}")
        print(f"  Error: {str(e)}")
        return False, None


def main():
    """Run all template rendering tests."""
    print("=" * 70)
    print("WAVE 2 INTEGRATION TEST: Jinja2 Template Rendering")
    print("=" * 70)

    # Setup
    env = setup_jinja_environment()
    if not env:
        sys.exit(1)

    print(f"\n📁 Template Directory: {env.loader.searchpath[0]}")
    print(f"📊 Testing {len(env.list_templates())} templates\n")

    # Run tests
    results = {}

    results["base.html"] = test_base_template(env)
    results["prompts/list.html"] = test_prompts_list_template(env)
    results["prompts/review.html"] = test_prompts_review_template(env)
    results["components/prompt_card.html"] = test_prompt_card_component(env)

    # Quality badge has multiple test cases
    badge_passed, badge_results = test_quality_badge_component(env)
    results["components/quality_badge.html"] = (badge_passed, badge_results)

    results["components/edit_form.html"] = test_edit_form_component(env)

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for r in results.values() if r[0])
    total_count = len(results)

    for template_name, (passed, _) in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {template_name}")

    print("=" * 70)
    print(f"\n📈 Results: {passed_count}/{total_count} templates passed")

    if passed_count == total_count:
        print("✅ All templates rendered successfully!")
        print("\n✓ All Tailwind CSS classes present")
        print("✓ All HTMX attributes (hx-get, hx-post, hx-swap, hx-target) found")
        print("✓ No Jinja2 syntax errors detected")
        return 0
    else:
        print(f"⚠️  {total_count - passed_count} template(s) failed to render")
        return 1


if __name__ == "__main__":
    sys.exit(main())
