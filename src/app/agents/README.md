# Multi-Agent AI System for Mochi Donut

This directory contains the complete multi-agent AI architecture for generating high-quality spaced repetition flashcards using LangGraph and LangChain.

## Architecture Overview

The system implements an **Orchestrator-Workers pattern** with specialized agents:

1. **ContentAnalyzerAgent** - Extracts key concepts using GPT-5-nano
2. **PromptGeneratorAgent** - Creates prompts following Matuschak's principles using GPT-5-mini
3. **QualityReviewerAgent** - Evaluates prompt quality using GPT-5-standard
4. **RefinementAgent** - Iteratively improves prompts using GPT-5-mini
5. **OrchestratorAgent** - Coordinates the workflow between agents

## Cost-Optimized Model Selection (2025)

- **GPT-5-nano** ($0.05/1M input): Simple extraction, classification
- **GPT-5-mini** ($0.25/1M input): Prompt generation, refinement
- **GPT-5-standard** ($1.25/1M input): Complex analysis, quality review

## Key Features

### LangGraph Workflow
- Graph-based agent orchestration with proper state transitions
- Conditional edges based on quality scores and iteration limits
- Automatic fallback to orchestrator if LangGraph unavailable

### Quality Assessment
- Comprehensive evaluation against Andy Matuschak's principles:
  - Focused and specific targeting
  - Precise, unambiguous language
  - Appropriate cognitive load
  - Meaningful retrieval practice
  - Sufficient contextual cues
- LLM-as-judge pattern for objective quality scoring

### Cost Tracking
- Real-time cost monitoring across all model usage
- Per-workflow cost limits and estimates
- Detailed breakdown by model and operation

### Error Handling
- Retry logic with exponential backoff
- Graceful degradation and fallback strategies
- Comprehensive error logging and recovery

## Usage Examples

### Basic Prompt Generation

```python
from app.agents.service import AgentOrchestratorService
from app.schemas.prompt import PromptGenerationRequest

# Initialize service
service = AgentOrchestratorService(content_repo, prompt_repo, db_session)

# Generate prompts
request = PromptGenerationRequest(
    content_id=content_id,
    target_count=10,
    async_processing=False
)

response = await service.generate_prompts(request)

if response.success:
    print(f"Generated {len(response.prompts)} prompts")
    for prompt in response.prompts:
        print(f"Q: {prompt['question']}")
        print(f"A: {prompt['answer']}")
        print(f"Quality: {prompt['confidence_score']:.2f}")
```

### Streaming Workflow with Progress Updates

```python
async def stream_generation():
    request = PromptGenerationRequest(content_id=content_id)

    async for update in service.generate_prompts_stream(request):
        if update["type"] == "progress":
            print(f"Stage: {update['stage']} - {update['message']}")
        elif update["type"] == "completed":
            print(f"Generated {len(update['prompts'])} prompts")
        elif update["type"] == "error":
            print(f"Error: {update['message']}")
```

### Content Analysis Preview

```python
# Preview analysis without generating prompts
preview = await service.preview_content_analysis(content_id)

print(f"Key concepts: {preview['analysis']['key_concepts']}")
print(f"Difficulty: {preview['analysis']['difficulty_level']}/5")
print(f"Recommended prompts: {preview['analysis']['recommended_prompt_count']}")
```

### Cost Estimation

```python
# Get cost estimate before processing
estimate = await service.get_cost_estimate(content_id, target_prompts=15)

print(f"Estimated cost: ${estimate['estimated_total_cost']:.4f}")
print(f"Within budget: {estimate['within_budget']}")
print("Cost breakdown:")
for operation, cost in estimate['cost_breakdown'].items():
    print(f"  {operation}: ${cost:.4f}")
```

### Direct Agent Usage

```python
from app.agents.content_analyzer import ContentAnalyzerAgent
from app.agents.prompt_generator import PromptGeneratorAgent

# Analyze content directly
analyzer = ContentAnalyzerAgent()
analysis = await analyzer.analyze_content_preview(content_text)

# Generate single prompt
generator = PromptGeneratorAgent()
prompt = await generator.generate_single_prompt(
    concept="Machine Learning",
    context=content_text,
    difficulty=3
)
```

### Quality Review

```python
from app.agents.quality_reviewer import QualityReviewerAgent

reviewer = QualityReviewerAgent(quality_threshold=0.7)
quality_result = await reviewer.review_single_prompt(prompt_data)

print(f"Overall score: {quality_result['overall_score']:.2f}")
print(f"Needs revision: {quality_result['needs_revision']}")
print(f"Key issues: {quality_result['key_issues']}")
```

## Configuration

The system is configured through `config.py`:

```python
from app.agents.config import agent_config

# Adjust quality threshold
agent_config.workflow.quality_threshold = 0.8

# Set cost limits
agent_config.workflow.cost_limit_per_workflow = 2.0

# Enable/disable features
agent_config.enable_langgraph = True
agent_config.enable_cost_tracking = True
```

## Integration with FastAPI

### Endpoint Integration

```python
from fastapi import APIRouter, Depends
from app.agents.service import AgentOrchestratorService

router = APIRouter()

@router.post("/generate-prompts")
async def generate_prompts(
    request: PromptGenerationRequest,
    service: AgentOrchestratorService = Depends(get_agent_service)
):
    return await service.generate_prompts(request)

@router.get("/preview/{content_id}")
async def preview_analysis(
    content_id: UUID,
    service: AgentOrchestratorService = Depends(get_agent_service)
):
    return await service.preview_content_analysis(content_id)
```

### Dependency Injection

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_agent_service(
    db: AsyncSession = Depends(get_db)
) -> AgentOrchestratorService:
    content_repo = ContentRepository(db)
    prompt_repo = PromptRepository(db)
    return AgentOrchestratorService(content_repo, prompt_repo, db)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all agent tests
pytest src/app/agents/test_agents.py -v

# Test specific agent
pytest src/app/agents/test_agents.py::TestContentAnalyzerAgent -v

# Test with coverage
pytest src/app/agents/test_agents.py --cov=app.agents --cov-report=html
```

## Monitoring and Observability

### Cost Tracking

```python
# Get workflow cost summary
workflow_result = await service.generate_prompts(request)
cost_summary = workflow_result.metadata.get("cost_summary", {})

print(f"Total cost: ${cost_summary['total_cost']:.4f}")
print(f"Model breakdown: {cost_summary['model_breakdown']}")
```

### Quality Analytics

```python
# Get quality analytics for content
analytics = await service.get_quality_analytics(content_id)

print(f"Average quality: {analytics['average_quality']:.2f}")
print(f"Above threshold: {analytics['above_threshold']}/{analytics['total_prompts']}")
print(f"Quality by type: {analytics['quality_by_type']}")
```

### Error Handling

The system provides comprehensive error handling:

```python
try:
    result = await service.generate_prompts(request)
    if not result.success:
        print(f"Generation failed: {result.message}")
        print(f"Error details: {result.metadata.get('error')}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Performance Optimization

### Caching
- Model response caching for repeated content
- 90% cost reduction for recently processed content
- Configurable cache TTL and size limits

### Concurrent Processing
- Batch processing for multiple content items
- Configurable concurrency limits
- Queue management for high-volume workflows

### Resource Management
- Automatic timeout handling
- Memory-efficient processing for large content
- Connection pooling for external APIs

## Security Considerations

### Input Validation
- Comprehensive Pydantic validation for all inputs
- Content size limits and sanitization
- Rate limiting and user authentication

### Output Filtering
- Quality score validation before storage
- Content filtering for inappropriate material
- Audit logging for all agent interactions

### Cost Protection
- Per-workflow cost limits
- User-based budget controls
- Automatic workflow termination on cost overruns

## Production Deployment

### Environment Configuration

```bash
# Required environment variables
OPENAI_API_KEY=your_openai_key
AGENT_QUALITY_THRESHOLD=0.7
AGENT_MAX_ITERATIONS=3
AGENT_COST_LIMIT=5.0
ENVIRONMENT=production
```

### Scaling Considerations

- Use async processing for high-volume workloads
- Configure appropriate timeout values
- Monitor cost accumulation across users
- Implement proper error handling and recovery

### Monitoring Integration

The system integrates with logging and monitoring systems:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.agents")

# All agent operations are automatically logged
# Integrate with your monitoring solution (DataDog, New Relic, etc.)
```

## Future Enhancements

### Planned Features
- Multi-language support for international content
- Custom quality criteria configuration
- Advanced caching strategies
- Real-time collaboration features
- Integration with additional LLM providers

### Model Upgrades
- Support for newer GPT models as available
- Integration with other model providers (Anthropic, Google)
- Custom fine-tuned models for domain-specific content

### Workflow Enhancements
- Parallel agent execution for improved performance
- Advanced retry strategies with circuit breakers
- Dynamic quality threshold adjustment
- A/B testing framework for prompt variations