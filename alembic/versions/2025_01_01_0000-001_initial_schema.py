"""Initial schema creation with all models

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database to this revision."""

    # Create contents table
    op.create_table(
        'contents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('source_type', sa.Enum('WEB', 'PDF', 'YOUTUBE', 'NOTION', 'RAINDROP', 'MARKDOWN', name='sourcetype'), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('markdown_content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('chroma_collection', sa.String(length=255), nullable=True),
        sa.Column('chroma_document_id', sa.String(length=255), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('estimated_reading_time', sa.Integer(), nullable=True),
        sa.Column('processing_status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'SKIPPED', name='processingstatus'), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('processing_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_hash')
    )

    # Create indexes for contents table
    op.create_index('ix_content_chroma', 'contents', ['chroma_collection', 'chroma_document_id'])
    op.create_index('ix_content_created_at', 'contents', ['created_at'])
    op.create_index('ix_content_hash', 'contents', ['content_hash'])
    op.create_index('ix_content_source_type', 'contents', ['source_type'])
    op.create_index('ix_content_status', 'contents', ['processing_status'])
    op.create_index('ix_contents_id', 'contents', ['id'])

    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('prompt_type', sa.Enum('FACTUAL', 'PROCEDURAL', 'CONCEPTUAL', 'OPEN_LIST', 'CLOZE_DELETION', name='prompttype'), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_edited', sa.Boolean(), nullable=True),
        sa.Column('edit_reason', sa.String(length=500), nullable=True),
        sa.Column('mochi_card_id', sa.String(length=255), nullable=True),
        sa.Column('mochi_deck_id', sa.String(length=255), nullable=True),
        sa.Column('mochi_status', sa.String(length=50), nullable=True),
        sa.Column('source_context', sa.Text(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_to_mochi_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for prompts table
    op.create_index('ix_prompt_confidence', 'prompts', ['confidence_score'])
    op.create_index('ix_prompt_content_id', 'prompts', ['content_id'])
    op.create_index('ix_prompt_content_type', 'prompts', ['content_id', 'prompt_type'])
    op.create_index('ix_prompt_created_at', 'prompts', ['created_at'])
    op.create_index('ix_prompt_mochi_card', 'prompts', ['mochi_card_id'])
    op.create_index('ix_prompt_type', 'prompts', ['prompt_type'])
    op.create_index('ix_prompts_id', 'prompts', ['id'])

    # Create quality_metrics table
    op.create_table(
        'quality_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.Enum('FOCUS_SPECIFICITY', 'PRECISION_CLARITY', 'COGNITIVE_LOAD', 'RETRIEVAL_PRACTICE', 'OVERALL_QUALITY', name='qualitymetrictype'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('evaluator_model', sa.String(length=100), nullable=True),
        sa.Column('evaluation_prompt', sa.Text(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('feedback', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for quality_metrics table
    op.create_index('ix_quality_metric_prompt', 'quality_metrics', ['prompt_id'])
    op.create_index('ix_quality_metric_prompt_type', 'quality_metrics', ['prompt_id', 'metric_type'])
    op.create_index('ix_quality_metric_score', 'quality_metrics', ['score'])
    op.create_index('ix_quality_metric_type', 'quality_metrics', ['metric_type'])

    # Create agent_executions table
    op.create_table(
        'agent_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_type', sa.Enum('ORCHESTRATOR', 'CONTENT_ANALYSIS', 'PROMPT_GENERATION', 'QUALITY_REVIEW', 'REFINEMENT', name='agenttype'), nullable=False),
        sa.Column('execution_id', sa.String(length=255), nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('model_used', sa.String(length=100), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for agent_executions table
    op.create_index('ix_agent_execution_content', 'agent_executions', ['content_id'])
    op.create_index('ix_agent_execution_id', 'agent_executions', ['execution_id'])
    op.create_index('ix_agent_execution_started', 'agent_executions', ['started_at'])
    op.create_index('ix_agent_execution_status', 'agent_executions', ['status'])
    op.create_index('ix_agent_execution_type', 'agent_executions', ['agent_type'])

    # Create user_interactions table
    op.create_table(
        'user_interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('interaction_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('before_value', sa.Text(), nullable=True),
        sa.Column('after_value', sa.Text(), nullable=True),
        sa.Column('change_reason', sa.String(length=500), nullable=True),
        sa.Column('satisfaction_score', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for user_interactions table
    op.create_index('ix_user_interaction_created', 'user_interactions', ['created_at'])
    op.create_index('ix_user_interaction_prompt', 'user_interactions', ['prompt_id'])
    op.create_index('ix_user_interaction_session', 'user_interactions', ['session_id'])
    op.create_index('ix_user_interaction_type', 'user_interactions', ['interaction_type'])

    # Create processing_queue table
    op.create_table(
        'processing_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_type', sa.String(length=100), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for processing_queue table
    op.create_index('ix_queue_created', 'processing_queue', ['created_at'])
    op.create_index('ix_queue_scheduled', 'processing_queue', ['scheduled_at'])
    op.create_index('ix_queue_status_priority', 'processing_queue', ['status', 'priority'])
    op.create_index('ix_queue_task_type', 'processing_queue', ['task_type'])


def downgrade() -> None:
    """Downgrade database from this revision."""

    # Drop all tables in reverse order (respecting foreign keys)
    op.drop_table('processing_queue')
    op.drop_table('user_interactions')
    op.drop_table('agent_executions')
    op.drop_table('quality_metrics')
    op.drop_table('prompts')
    op.drop_table('contents')

    # Drop custom enum types
    op.execute('DROP TYPE IF EXISTS agenttype')
    op.execute('DROP TYPE IF EXISTS qualitymetrictype')
    op.execute('DROP TYPE IF EXISTS prompttype')
    op.execute('DROP TYPE IF EXISTS processingstatus')
    op.execute('DROP TYPE IF EXISTS sourcetype')