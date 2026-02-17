"""Background worker for processing queued workflow dispatches."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .config import settings
from .database import async_session_factory
from .engine.runner import WorkflowRunner
from .services.dispatch_svc import (
    claim_next_dispatch,
    mark_dispatch_completed,
    mark_dispatch_failed,
)

logger = logging.getLogger(__name__)


class DispatchWorker:
    """Polls and executes queued workflow dispatch records."""

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        if self._task is not None or not settings.dispatch_worker_enabled:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="workflow-dispatch-worker")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = False
            try:
                async with async_session_factory() as db:
                    dispatch = await claim_next_dispatch(db)
                    if dispatch:
                        processed = True
                        runner = WorkflowRunner(db)
                        try:
                            execution = await runner.run(
                                dispatch.workflow_id,
                                trigger_data=dispatch.trigger_data,
                            )
                            await mark_dispatch_completed(db, dispatch, execution.id)
                        except Exception as exc:  # pragma: no cover - defensive log path
                            logger.exception("Dispatch execution failed")
                            await mark_dispatch_failed(db, dispatch, str(exc))
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive log path
                logger.exception("Dispatch worker loop failed")

            if not processed:
                await asyncio.sleep(settings.dispatch_poll_interval_seconds)


dispatch_worker = DispatchWorker()

