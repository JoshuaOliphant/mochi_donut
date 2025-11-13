# AI Developer Workflows (ADWs) for Mochi Donut

This directory contains the ADW infrastructure for programmatic Claude Code orchestration.

## What Are ADWs?

ADWs (AI Developer Workflows) enable you to execute Claude Code prompts programmatically, creating reproducible development workflows with structured observability. Think of it as "code that writes code" - but with AI agents doing the heavy lifting.

## Quick Start

### Mode A: Claude Max Subscription (Recommended)

If you have Claude Max, just start using ADWs - no configuration needed!

```bash
# Try your first prompt
./adw_prompt.py "What is the Mochi Donut architecture?"

# Plan and implement a small task
./adw_chore_implement.py "Add logging to the content processor"

# Break down a large feature
./adw_plan_tdd.py "Implement batch content processing"
```

### Mode B: API-Based (For Automation)

For CI/CD or automated workflows:

```bash
# Create .env file
cp .env.sample .env

# Add your API key
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

## Directory Structure

```
adws/
├── adw_modules/
│   └── agent.py              # Core execution engine
├── adw_prompt.py             # Execute adhoc prompts
├── adw_slash_command.py      # Execute slash commands
├── adw_chore_implement.py    # Plan + implement workflow
├── adw_plan_tdd.py           # TDD planning for large tasks
├── .env.sample               # Configuration template
└── README.md                 # This file
```

## Core Scripts

### `adw_prompt.py` - Adhoc Prompts

Execute any prompt programmatically:

```bash
./adw_prompt.py "Analyze the agent orchestration pattern"
./adw_prompt.py "Suggest optimizations for Chroma queries" --model opus
./adw_prompt.py "Help me debug this error" --no-retry
```

**Use when:** You need quick answers or want to explore ideas.

### `adw_slash_command.py` - Template Execution

Execute structured slash command templates from `.claude/commands/`:

```bash
./adw_slash_command.py /chore abc123 "add error handling"
./adw_slash_command.py /implement specs/chore-abc123-*.md
./adw_slash_command.py /prime  # Load project context
./adw_slash_command.py /feature def456 "batch processing"
```

**Use when:** You want reproducible, template-based workflows.

### `adw_chore_implement.py` - Compound Workflow

Plan AND implement in one command:

```bash
./adw_chore_implement.py "Fix the Mochi API timeout issue"
./adw_chore_implement.py "Add caching to agent responses" --model opus
```

**Use when:** You want end-to-end automation for small-to-medium tasks.

**What it does:**
1. Runs `/chore` to create a plan
2. Extracts the plan file path
3. Runs `/implement` with the plan
4. Returns structured output for both phases

### `adw_plan_tdd.py` - TDD Planning

Break down large specifications into GitHub issue-sized tasks:

```bash
./adw_plan_tdd.py "Add OAuth2 authentication"
./adw_plan_tdd.py specs/feature-auth.md --spec-file
./adw_plan_tdd.py "Build real-time sync system" --model opus
```

**Use when:** You need to break down large features into manageable tasks.

**Output:** `specs/plans/plan-{id}.md` with:
- Task breakdown (Size S/M/L for agent execution)
- Dependency graph
- Implementation phases
- TDD guidance for each task
- Acceptance criteria

## Available Slash Commands

Commands are defined in `.claude/commands/`:

- **`/chore`** - Plan small tasks and fixes
- **`/implement`** - Execute implementation plans
- **`/feature`** - Plan comprehensive features
- **`/plan-tdd`** - Break down large specs into TDD tasks
- **`/prime`** - Load Mochi Donut context

## Model Selection

Choose the right model for your task:

- **`haiku`** - Fast & economical (~$0.25/1M input)
  - Simple tasks, quick fixes, code generation
- **`sonnet`** (default) - Balanced (~$3/1M input)
  - Most workflows, standard planning
- **`opus`** - Maximum capability (~$15/1M input)
  - Complex architecture, critical decisions

Add `--model opus` to any command to use the most capable model.

## Observability

All executions create structured output in `../agents/{adw_id}/{agent_name}/`:

```
agents/abc12345/
├── planner/
│   ├── cc_raw_output.jsonl         # Raw JSONL stream from Claude Code
│   ├── cc_raw_output.json          # Parsed messages as JSON array
│   ├── cc_final_object.json        # Final result object
│   ├── custom_summary_output.json  # High-level execution summary
│   └── prompts/
│       └── chore.txt               # Saved prompt for reproducibility
└── builder/
    └── ...                         # Same structure for build phase
```

**Benefits:**
- Debug failed workflows
- Analyze agent behavior
- Reproduce execution results
- Track costs per execution

## Current Phase: Enhanced

You have the **Enhanced Phase** setup with:

✅ Core subprocess execution
✅ CLI wrappers for adhoc and template prompts
✅ Compound workflows (plan + implement)
✅ TDD planning for large tasks
✅ Rich slash command templates

## Future: Scaled Phase

When ready for production-scale workflows, upgrade to **Scaled Phase** for:

- **Beads Integration**: Local SQLite issue tracking (offline-first)
- **Git Worktree Isolation**: Safe parallel workflow execution
- **State Management**: Track workflow progress
- **GitHub/Beads Integration**: Automated issue/PR management
- **Workflow Composition**: Complex multi-phase SDLC workflows

Since you chose **Beads** for issue tracking, the Scaled upgrade will add:
- `adws/adw_modules/beads_integration.py` - Beads CLI integration
- `adws/adw_beads_ready.py` - Interactive task picker
- Slash commands: `/classify_issue`, `/install_worktree`, `/bug`
- Workflow scripts: `adw_sdlc_iso.py`, `adw_ship_iso.py`

**Beads Benefits:**
- Work completely offline
- Faster than GitHub API calls
- SQLite-based local storage
- No network dependency
- Perfect for local dev flow

## Common Workflows

### Quick Fix
```bash
./adw_chore_implement.py "Fix the async session handling bug"
```

### Feature Development
```bash
# 1. Break down the feature
./adw_plan_tdd.py "Add batch content processing"

# 2. Review the plan
cat ../specs/plans/plan-*.md

# 3. Implement tasks from the plan
# (Use the task descriptions to create chores)
```

### Context-Heavy Task
```bash
# Prime Claude with project context first
./adw_slash_command.py /prime

# Then do the complex task
./adw_prompt.py "Design a new quality scoring agent" --model opus
```

## Troubleshooting

### "Claude Code CLI not found"

Make sure Claude Code is installed:
```bash
claude --version
```

If not, install from: https://claude.ai/code

### "Permission denied"

Make scripts executable:
```bash
chmod +x adw_*.py
```

### Import errors

The scripts use uv inline dependencies (PEP 723), which auto-install on first run.

### "No API key found" (API mode)

Create `.env` file:
```bash
cp .env.sample .env
# Add: ANTHROPIC_API_KEY=sk-ant-...
```

## Best Practices

1. **Use the right model for the task**
   - Haiku for simple tasks
   - Sonnet for most work
   - Opus for critical decisions

2. **Check observability output**
   - Review `agents/{id}/` directories after execution
   - Analyze costs in `custom_summary_output.json`

3. **Start small, scale up**
   - Try `adw_prompt.py` first
   - Then `adw_chore_implement.py`
   - Finally `adw_plan_tdd.py` for large features

4. **Keep plans in version control**
   - Commit `specs/` directory
   - Plans are documentation too!

5. **Use /prime for complex tasks**
   - Loads project context
   - Improves agent understanding
   - Worth the extra tokens for better results

## Need Help?

- Read `../CLAUDE.md` for comprehensive ADW documentation
- Check `.claude/commands/*.md` for slash command templates
- Review `../specs/plans/README.md` for TDD planning details
- Examine `adw_modules/agent.py` for implementation patterns

## Contributing

When extending ADWs:
1. Follow existing patterns in `agent.py`
2. Use Rich for CLI output
3. Create structured observability outputs
4. Document new slash commands in `.claude/commands/`
5. Update this README

Happy AI-driven development! 🚀
