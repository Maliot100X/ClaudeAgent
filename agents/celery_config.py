"""Celery configuration for distributed task queue.

Uses Redis as both broker and backend.
"""

import os
from typing import Optional
from celery import Celery
from kombu import Queue, Exchange

# Celery app configuration
app = Celery('ai_agent_platform')

# Broker and backend (Redis)
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
app.conf.broker_url = redis_url
app.conf.result_backend = redis_url

# Serialization
app.conf.task_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.result_serializer = 'json'

# Task execution settings
app.conf.task_track_started = True
app.conf.task_time_limit = 3600  # 1 hour max
app.conf.task_soft_time_limit = 3300  # Soft limit warning at 55 minutes
app.conf.worker_prefetch_multiplier = 1  # One task at a time per worker

# Result backend settings
app.conf.result_expires = 86400  # Results expire after 24 hours
app.conf.result_extended = True

# Task routing
app.conf.task_default_queue = 'default'
app.conf.task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('signals', Exchange('signals'), routing_key='signals'),
    Queue('analysis', Exchange('analysis'), routing_key='analysis'),
    Queue('market_data', Exchange('market_data'), routing_key='market_data'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications'),
)

app.conf.task_routes = {
    'tasks.market_data.*': {'queue': 'market_data'},
    'tasks.signals.*': {'queue': 'signals'},
    'tasks.analysis.*': {'queue': 'analysis'},
    'tasks.notifications.*': {'queue': 'notifications'},
}

# Scheduling (beat schedule)
app.conf.beat_schedule = {
    'fetch-market-data': {
        'task': 'tasks.market_data.fetch_prices',
        'schedule': 60.0,  # Every minute
    },
    'cleanup-old-results': {
        'task': 'tasks.maintenance.cleanup_results',
        'schedule': 3600.0,  # Every hour
    },
}

# Redis connection settings
app.conf.broker_connection_retry = True
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_max_retries = 10

# Worker settings
app.conf.worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks
app.conf.worker_max_memory_per_child = 512000  # 512MB max per worker

# Monitoring
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True

# Import tasks
app.autodiscover_tasks([
    'agents.task_queue',
    'skills',
])


@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f'Request: {self.request!r}')
    return {'status': 'ok', 'task_id': self.request.id}


def get_celery_app() -> Celery:
    """Get the configured Celery application."""
    return app


def start_worker(
    queues: Optional[list] = None,
    loglevel: str = 'info',
    concurrency: int = 4
) -> None:
    """Start a Celery worker programmatically."""
    argv = [
        'worker',
        '--loglevel=' + loglevel,
        '--concurrency=' + str(concurrency),
    ]

    if queues:
        argv.append('--queues=' + ','.join(queues))

    app.worker_main(argv)


def start_beat(loglevel: str = 'info') -> None:
    """Start the Celery beat scheduler."""
    argv = [
        'beat',
        '--loglevel=' + loglevel,
    ]
    app.worker_main(argv)