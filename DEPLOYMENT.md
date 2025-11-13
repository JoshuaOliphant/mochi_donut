# Deployment Guide for Mochi Donut

This guide covers the complete deployment process for the Mochi Donut spaced repetition learning system using Fly.io, Docker, and modern Python deployment practices.

## Overview

Mochi Donut is deployed using:
- **Fly.io** for application hosting with auto-scaling
- **Docker** with multi-stage builds and uv package manager
- **SQLite + Litestream** for database with persistent volumes
- **Redis** for Celery task queues and caching
- **Chroma Cloud** for vector database storage
- **GitHub Actions** for CI/CD pipeline

## Prerequisites

### Required Tools
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Install Docker
# Follow instructions at: https://docs.docker.com/get-docker/

# Install uv (for local development)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Required Accounts
- **Fly.io Account**: Sign up at https://fly.io
- **OpenAI Account**: For GPT-5 model access
- **Mochi Account**: For flashcard integration
- **Chroma Cloud** (optional): For production vector storage

## Initial Setup

### 1. Fly.io App Creation

```bash
# Authenticate with Fly.io
flyctl auth login

# Create new app (run from project root)
flyctl apps create mochi-donut

# Create persistent volume for SQLite database
flyctl volumes create mochi_donut_data --region iad --size 10

# Create Redis instance (or use external Redis)
flyctl redis create --name mochi-donut-redis
```

### 2. Environment Variables and Secrets

Set production secrets via Fly.io (never commit these to Git):

```bash
# Required secrets
flyctl secrets set SECRET_KEY="your-super-secret-key-here" --app mochi-donut
flyctl secrets set OPENAI_API_KEY="sk-your-openai-api-key" --app mochi-donut
flyctl secrets set MOCHI_API_KEY="your-mochi-api-key" --app mochi-donut

# Optional secrets
flyctl secrets set JINA_API_KEY="your-jina-api-key" --app mochi-donut
flyctl secrets set CHROMA_API_KEY="your-chroma-cloud-key" --app mochi-donut

# Verify secrets are set
flyctl secrets list --app mochi-donut
```

### 3. GitHub Secrets (for CI/CD)

Set these secrets in your GitHub repository settings:

```
FLY_API_TOKEN=<your-fly-api-token>
OPENAI_API_KEY=<your-openai-api-key>
MOCHI_API_KEY=<your-mochi-api-key>
```

## Deployment Methods

### Method 1: Automated Deployment (Recommended)

Push to main branch triggers automatic deployment:

```bash
# Commit your changes
git add .
git commit -m "Deploy to production"
git push origin main

# GitHub Actions will:
# 1. Run tests
# 2. Build Docker image
# 3. Deploy to Fly.io
# 4. Run health checks
```

### Method 2: Manual Deployment

Use the production deployment script:

```bash
# Make script executable
chmod +x scripts/production/deploy.sh

# Run full deployment
./scripts/production/deploy.sh

# Or run specific operations
./scripts/production/deploy.sh check    # Pre-deployment checks
./scripts/production/deploy.sh test     # Run tests only
./scripts/production/deploy.sh health   # Health checks only
```

### Method 3: Direct Fly.io Deployment

```bash
# Deploy directly with flyctl
flyctl deploy --remote-only

# Monitor deployment
flyctl status
flyctl logs
```

## Database Migrations

### Running Migrations

```bash
# Check migration status
./scripts/production/migrate.sh status

# Run pending migrations
./scripts/production/migrate.sh migrate

# View migration history
./scripts/production/migrate.sh history
```

### Creating New Migrations

```bash
# Generate migration locally
./scripts/production/migrate.sh generate "Add new feature"

# Review generated migration file
# Commit and deploy via normal process
```

### Rollback Procedures

```bash
# Rollback one migration
./scripts/production/migrate.sh rollback -1

# Rollback to specific revision
./scripts/production/migrate.sh rollback abc123

# Restore from backup
./scripts/production/migrate.sh rollback current backup_file.gz
```

## Backup and Restore

### Creating Backups

```bash
# Create database backup
./scripts/production/backup.sh backup

# List available backups
./scripts/production/backup.sh list

# Create backup before major changes
./scripts/production/backup.sh backup
```

### Restoring from Backup

```bash
# Restore from specific backup
./scripts/production/backup.sh restore backup_file.gz

# Export for migration
./scripts/production/backup.sh export
```

## Monitoring and Maintenance

### Health Checks

```bash
# Application health
curl https://mochi-donut.fly.dev/health

# Detailed health (includes dependencies)
curl https://mochi-donut.fly.dev/health/detailed

# Prometheus metrics
curl https://mochi-donut.fly.dev/metrics/prometheus
```

### Log Monitoring

```bash
# Real-time logs
flyctl logs --app mochi-donut

# Specific service logs
flyctl logs --app mochi-donut | grep celery

# Historical logs
flyctl logs --app mochi-donut --since 1h
```

### Performance Monitoring

- **Fly.io Metrics**: Available at https://fly.io/apps/mochi-donut/monitoring
- **Prometheus Endpoint**: `/metrics/prometheus` for external monitoring
- **Logfire Integration**: Configured for application performance monitoring

### Scaling

```bash
# Scale horizontally
flyctl scale count 3 --app mochi-donut

# Scale vertically
flyctl scale vm shared-cpu-2x --app mochi-donut

# Auto-scaling is configured in fly.toml
# Scales based on CPU usage and request rate
```

## Production Architecture

### Application Components

1. **FastAPI Application**: Main web server with API endpoints
2. **Celery Workers**: Background task processing
   - Content processing worker
   - AI processing worker
   - External APIs worker
3. **Celery Beat**: Scheduled task runner
4. **Redis**: Message broker and result backend
5. **SQLite**: Primary database with persistent volume
6. **Chroma**: Vector database for content similarity

### Network Architecture

- **HTTPS Termination**: Handled by Fly.io edge
- **Health Checks**: Multiple endpoints for different purposes
- **Auto-scaling**: Based on CPU and request metrics
- **Geographic Distribution**: Single region (configurable)

### Security Features

- **TLS/HTTPS**: Enforced via Fly.io
- **Trusted Host Middleware**: Validates request origins
- **Rate Limiting**: Configured per endpoint
- **Secret Management**: Via Fly.io secrets (not environment files)
- **Non-root Container**: Application runs as non-privileged user

## Troubleshooting

### Common Issues

1. **App Won't Start**
   ```bash
   # Check logs
   flyctl logs --app mochi-donut

   # Check secrets
   flyctl secrets list --app mochi-donut

   # Verify database volume
   flyctl volumes list --app mochi-donut
   ```

2. **Migration Failures**
   ```bash
   # Check database connectivity
   flyctl ssh console --app mochi-donut
   sqlite3 /data/mochi_donut.db .tables

   # Validate migrations
   ./scripts/production/migrate.sh validate
   ```

3. **Performance Issues**
   ```bash
   # Check metrics
   curl https://mochi-donut.fly.dev/metrics

   # Monitor resource usage
   flyctl status --app mochi-donut

   # Scale if needed
   flyctl scale count 2 --app mochi-donut
   ```

### Emergency Procedures

1. **Immediate Rollback**
   ```bash
   # Rollback to previous release
   flyctl releases rollback --app mochi-donut
   ```

2. **Database Recovery**
   ```bash
   # Restore from latest backup
   ./scripts/production/backup.sh list
   ./scripts/production/backup.sh restore latest_backup.gz
   ```

3. **Service Recovery**
   ```bash
   # Restart all machines
   flyctl machine restart --app mochi-donut

   # Force restart if needed
   flyctl machine stop --app mochi-donut
   flyctl machine start --app mochi-donut
   ```

## Cost Optimization

### Resource Allocation

- **Shared CPU**: Start with `shared-cpu-1x` for development
- **Memory**: 1GB minimum for FastAPI + Celery workers
- **Storage**: 10GB persistent volume (expandable)
- **Auto-scaling**: Configured to minimize idle costs

### Expected Costs (Monthly)

- **Fly.io App**: $5-15 (shared CPU + storage)
- **Fly.io Redis**: $3-8 (depending on usage)
- **Chroma Cloud**: $8-15 (5GB storage)
- **Total**: ~$20-40/month for production

### Cost Monitoring

```bash
# Check current usage
flyctl status --app mochi-donut

# View billing
flyctl billing

# Monitor scaling metrics
flyctl metrics --app mochi-donut
```

## Development vs Production

### Key Differences

| Component | Development | Production |
|-----------|-------------|------------|
| Database | Local SQLite | SQLite + Persistent Volume |
| Redis | Docker container | Fly Redis / External |
| Chroma | Local instance | Chroma Cloud |
| Secrets | .env file | Fly.io secrets |
| HTTPS | Not enforced | Required |
| Scaling | Single instance | Auto-scaling |
| Monitoring | Basic logs | Full metrics + alerts |

### Environment Sync

```bash
# Copy production config template
cp env.production.sample .env.production

# Update with production values (without secrets)
# Secrets should only be set via flyctl secrets
```

## Security Best Practices

1. **Never commit secrets to Git**
2. **Use Fly.io secrets for sensitive data**
3. **Regularly rotate API keys**
4. **Monitor access logs**
5. **Keep dependencies updated**
6. **Use HTTPS everywhere**
7. **Validate all inputs**
8. **Implement rate limiting**

## Support and Resources

- **Fly.io Documentation**: https://fly.io/docs/
- **Application Logs**: `flyctl logs --app mochi-donut`
- **Health Dashboard**: https://mochi-donut.fly.dev/health/detailed
- **Monitoring Dashboard**: https://fly.io/apps/mochi-donut/monitoring

For deployment issues, check the logs first, then consult this guide's troubleshooting section.