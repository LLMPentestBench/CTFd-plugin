import logging
from typing import Callable

import gevent
from gevent.threadpool import ThreadPool

from CTFd.models import db
from . import utils
from .models import AgentRun, AgentRunStatus

class TaskQueue:
    """Generic polling worker pool that dequeues AgentRuns and dispatches them to a processor."""

    def __init__(self, processor: Callable[[AgentRun], None], pool_size: int):
        self._processor = processor
        self._pool_size = pool_size
        self._pool: ThreadPool | None = None

    @utils.wrap_app_context
    def _worker(self, i: int):
        logger = logging.getLogger(f"llmpentestbench.tq.worker.{i}")
        logger.info(f"Worker {i} started, waiting for tasks...")

        try:
            while True:
                agent_run = AgentRun.query.filter_by(_status=AgentRunStatus.QUEUED).order_by(AgentRun.id).first()
                if agent_run is None:
                    gevent.sleep(1)
                    continue

                rows_matched = AgentRun.query.filter_by(id=agent_run.id, _status=AgentRunStatus.QUEUED).update(
                    {"_status": AgentRunStatus.INITIATING},
                    synchronize_session=False,
                )
                if rows_matched == 0:
                    gevent.sleep(1)
                    continue

                db.session.commit()
                logger.info(f"Claimed run {agent_run.id} for processing")

                try:
                    self._processor(agent_run)
                except Exception as e:
                    logger.exception(f"Error processing run {agent_run.id}: {e}")
                    agent_run.mark_errored()
                logger.info(f"Finished processing run {agent_run.id}")
        except Exception:
            logger.exception("Error occurred while processing task")

    def start(self):
        if self._pool is not None:
            raise RuntimeError("TaskQueue already started")

        self._pool = ThreadPool(self._pool_size)
        for i in range(self._pool_size):
            self._pool.spawn(self._worker, i)
