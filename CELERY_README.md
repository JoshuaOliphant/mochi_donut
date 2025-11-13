# Celery Background Processing System for Mochi Donut

This document provides comprehensive information about the Celery background processing system implemented for the Mochi Donut spaced repetition learning platform.

## Overview

The Celery system handles all background processing tasks including:

- **Content Processing**: Web scraping, PDF processing, vector embeddings
- **AI Agent Operations**: Prompt generation, quality review, refinement
- **Mochi Synchronization**: Card creation, batch operations, deck management
- **Maintenance Tasks**: Data cleanup, analytics aggregation, health monitoring

## Architecture

### Task Queues

The system uses four specialized queues optimized for different workloads:

1. **`content_processing`** - Content extraction and processing (Priority: High)
2. **`ai_processing`** - AI model operations with cost optimization (Priority: Medium)
3. **`external_apis`** - Third-party API interactions with rate limiting (Priority: Medium)
4. **`maintenance`** - System maintenance and cleanup (Priority: Low)

### Worker Configuration

- **Content Workers**: 2 concurrent processes, moderate rate limiting
- **AI Workers**: 1 concurrent process, conservative rate limiting for cost control
- **External API Workers**: 2 concurrent processes, respects API limits
- **Maintenance Workers**: 1 concurrent process, low priority operations

## Task Types

### Content Processing Tasks

Located in `/src/app/tasks/content_tasks.py`:

- `process_url_content` - Complete URL processing pipeline
- `extract_content_jina` - JinaAI content extraction
- `generate_embeddings` - Vector embedding generation
- `detect_duplicates` - Semantic duplicate detection
- `batch_process_content` - Batch URL processing

### AI Agent Tasks

Located in `/src/app/tasks/agent_tasks.py`:

- `generate_prompts` - AI-powered prompt generation
- `review_prompt_quality` - Quality assessment using GPT-5
- `refine_prompts` - Iterative prompt improvement
- `orchestrate_content_pipeline` - Complete AI pipeline
- `track_ai_costs` - Cost monitoring and reporting

### Mochi Sync Tasks

Located in `/src/app/tasks/sync_tasks.py`:

- `create_mochi_card` - Single card creation
- `batch_sync_cards` - Batch card synchronization
- `sync_deck_metadata` - Deck information updates
- `verify_sync_status` - Sync verification and recovery
- `update_mochi_card` - Card updates

### Maintenance Tasks

Located in `/src/app/tasks/maintenance_tasks.py`:

- `cleanup_old_data` - Data retention management
- `invalidate_expired_cache` - Cache cleanup
- `aggregate_analytics` - Metrics aggregation
- `health_check` - System health monitoring

## Configuration

### Redis Setup

The system uses Redis for both message broker and result backend:

- **Broker**: `redis://localhost:6379/0`
- **Results**: `redis://localhost:6379/1`
- **Caching**: Integrated with application cache service

### Task Routing

Tasks are automatically routed to appropriate queues based on their type:

```python
TASK_ROUTES = {
    "app.tasks.content_tasks.*": {"queue": "content_processing"},
    "app.tasks.agent_tasks.*": {"queue": "ai_processing"},
    "app.tasks.sync_tasks.*": {"queue": "external_apis"},
    "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
}
```

### Scheduled Tasks

Celery Beat handles periodic tasks:

- **Analytics Aggregation**: Daily at 2 AM
- **Cache Cleanup**: Every 6 hours
- **Data Cleanup**: Weekly on Sunday at 3 AM
- **Health Checks**: Every 15 minutes
- **Sync Verification**: Daily at 1 AM
- **Cost Tracking**: Daily at 4 AM

## Deployment Options

### Development (Local)

1. **Start Redis**:
   ```bash
   redis-server
   ```

2. **Start Workers**:
   ```bash
   # Content processing worker
   python scripts/start_celery.py worker -q content_processing -c 2

   # AI processing worker
   python scripts/start_celery.py worker -q ai_processing -c 1

   # External APIs worker
   python scripts/start_celery.py worker -q external_apis -c 2

   # Maintenance worker
   python scripts/start_celery.py worker -q maintenance -c 1
   ```

3. **Start Beat Scheduler**:
   ```bash
   python scripts/start_celery.py beat
   ```

4. **Monitor with Flower**:
   ```bash
   python scripts/start_celery.py flower
   # Visit http://localhost:5555
   ```

### Development (Docker Compose)

```bash
# Start entire stack
docker-compose up

# Scale specific services
docker-compose up --scale celery-worker-content=2
docker-compose up --scale celery-worker-ai=1
```

### Production (Fly.io)

The system is configured for deployment on Fly.io with:

- Auto-scaling workers based on queue depth
- Persistent Redis with clustering
- Health checks and automatic restarts
- Centralized logging with Logfire

## API Integration

### FastAPI Endpoints

The system provides REST API endpoints in `/src/app/api/task_endpoints.py`:

#### Content Processing
- `POST /api/tasks/content/process-url` - Trigger URL processing
- `POST /api/tasks/content/batch-process` - Batch processing
- `POST /api/tasks/content/generate-embeddings/{content_id}` - Generate embeddings

#### AI Operations
- `POST /api/tasks/ai/generate-prompts` - Trigger prompt generation
- `POST /api/tasks/ai/review-quality` - Quality review
- `POST /api/tasks/ai/orchestrate-pipeline` - Complete pipeline

#### Mochi Sync
- `POST /api/tasks/mochi/create-card/{prompt_id}` - Create card
- `POST /api/tasks/mochi/batch-sync` - Batch sync
- `POST /api/tasks/mochi/sync-decks` - Sync deck metadata

#### Monitoring
- `GET /api/tasks/status/{task_id}` - Task status
- `GET /api/tasks/active` - Active tasks
- `GET /api/tasks/metrics/{task_name}` - Performance metrics
- `GET /api/tasks/dashboard` - Comprehensive dashboard

### Usage Examples

```python
# Trigger content processing
response = await client.post("/api/tasks/content/process-url", json={
    "url": "https://example.com/article",
    "options": {"force_refresh": False},
    "user_id": "user123"
})
task_id = response.json()["task_id"]

# Check task status
status = await client.get(f"/api/tasks/status/{task_id}")

# Wait for completion
result = await client.post(f"/api/tasks/wait/{task_id}?timeout=300")
```

## Monitoring and Observability

### Task Monitoring

The system includes comprehensive monitoring in `/src/app/tasks/monitoring.py`:

- **Progress Tracking**: Real-time progress for long-running tasks
- **Performance Metrics**: Execution time, success rates, error tracking
- **Error Notifications**: Automatic error reporting and alerting
- **Health Checks**: System component health monitoring

### Metrics Collection

Key metrics tracked:

- Task execution times and success rates
- AI model usage and costs
- Queue depths and processing rates
- System resource utilization
- API response times and error rates

### Logging

Structured logging with correlation IDs:

```python
logger.info(
    "Task completed",
    task_id=task_id,
    task_name=task_name,
    execution_time=execution_time,
    result_type=type(result).__name__
)
```

## Error Handling and Recovery

### Retry Policies

Different task types have optimized retry configurations:

- **Content Tasks**: 3 retries with exponential backoff
- **AI Tasks**: 2 retries with longer delays (cost consideration)
- **External APIs**: 5 retries with shorter delays
- **Maintenance**: 1 retry with long delay

### Dead Letter Queue

Failed tasks after all retries are logged and can be:

- Manually retried through the API
- Analyzed for pattern detection
- Used for system improvement

### Circuit Breakers

External service failures trigger circuit breakers:

- Temporary disabling of failing services
- Graceful degradation of functionality
- Automatic recovery when services restore

## Cost Optimization

### AI Model Selection

Intelligent model selection based on task complexity:

- **GPT-5 Nano** ($0.05/1M): Simple extraction and classification
- **GPT-5 Mini** ($0.25/1M): Standard prompt generation
- **GPT-5 Standard** ($1.25/1M): Complex analysis and quality review

### Caching Strategy

- 90% discount on cached inputs (OpenAI caching)
- Redis caching for processed content
- Vector similarity caching for duplicate detection
- Deck metadata caching for Mochi operations

### Rate Limiting

Intelligent rate limiting prevents cost spikes:

- AI operations: 5 requests/minute
- Content processing: 10 requests/minute
- External APIs: 20 requests/minute (within limits)

## Testing

### Unit Tests

```bash
# Test individual tasks
uv run pytest tests/test_tasks/test_content_tasks.py -v

# Test with mocked external services
uv run pytest tests/test_tasks/ --mock-external -v
```

### Integration Tests

```bash
# Test complete workflows
uv run pytest tests/test_integration/test_celery_workflows.py -v

# Test with real Redis
uv run pytest tests/test_integration/ --redis-url redis://localhost:6379/15 -v
```

### Load Testing

```bash
# Simulate high task load
python scripts/load_test_celery.py --tasks 100 --concurrent 10
```

## Troubleshooting

### Common Issues

1. **Redis Connection Errors**
   ```bash
   # Check Redis status
   redis-cli ping

   # Check configuration
   python -c "from app.tasks.celery_app import celery_health_check; print(celery_health_check())"
   ```

2. **Worker Not Processing Tasks**
   ```bash
   # Check worker status
   python scripts/start_celery.py status

   # Check queue lengths
   uv run celery -A app.tasks inspect active_queues
   ```

3. **High Memory Usage**
   ```bash
   # Reduce max_tasks_per_child
   python scripts/start_celery.py worker --max-tasks-per-child=100
   ```

4. **AI Cost Spikes**
   ```bash
   # Check cost tracking
   curl localhost:8080/api/tasks/metrics/track_ai_costs

   # Reduce AI task rate limits in celery_app.py
   ```

### Debugging

Enable debug logging:

```bash
export CELERY_LOG_LEVEL=DEBUG
python scripts/start_celery.py worker --loglevel=debug
```

Monitor with Flower:

```bash
python scripts/start_celery.py flower
# Visit http://localhost:5555 for real-time monitoring
```

## Performance Tuning

### Worker Scaling

Adjust worker counts based on workload:

```bash
# High content processing load
docker-compose up --scale celery-worker-content=4

# High AI processing load (be careful with costs)
docker-compose up --scale celery-worker-ai=2
```

### Memory Optimization

- Set appropriate `max_tasks_per_child` values
- Use connection pooling for database operations
- Enable Redis memory optimization settings

### Network Optimization

- Use connection pooling for external APIs
- Implement request batching where possible
- Cache frequently accessed data

## Security Considerations

### API Keys

- All API keys stored in environment variables
- Rotation support for long-running deployments
- Secure key management in production

### Task Isolation

- Tasks run in separate processes
- No shared state between tasks
- Secure serialization of task parameters

### Network Security

- Redis authentication in production
- TLS for all external API calls
- Rate limiting to prevent abuse

## Future Enhancements

### Planned Improvements

1. **Advanced Scheduling**: More sophisticated task scheduling based on system load
2. **Dynamic Scaling**: Automatic worker scaling based on queue metrics
3. **Enhanced Monitoring**: Integration with Prometheus and Grafana
4. **Task Prioritization**: Priority-based task execution
5. **Workflow Engine**: Visual workflow designer for complex task chains

### Extension Points

The system is designed for extensibility:

- Plugin architecture for new task types
- Custom queue configurations
- Integration with additional message brokers
- Support for additional AI models

## Support and Maintenance

### Regular Maintenance

- Monitor error rates and adjust retry policies
- Review and optimize AI model usage
- Update external service integrations
- Clean up old monitoring data

### Capacity Planning

- Monitor queue depths and processing rates
- Plan worker scaling based on growth projections
- Estimate costs for different usage scenarios
- Review and optimize resource allocation

For additional support or questions, refer to the project documentation or create an issue in the repository.