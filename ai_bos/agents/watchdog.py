"""Watchdog — detects loops, deadlocks, and stalled agents.

Runs as a background thread (not Celery) so it is always on.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ai_bos.logging_config import log

STALL_TIMEOUT_SECONDS = 600    # 10 minutes
LOOP_WINDOW_SECONDS = 60


@dataclass
class TaskRecord:
    task_id: str
    agent_type: str
    started_at: datetime
    last_heartbeat: datetime
    action_key: str = ""          # tool + params signature for loop detection


class AgentWatchdog:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._action_history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        log.info("watchdog.started")

    def stop(self) -> None:
        self._stop_event.set()

    def register_task(self, task_id: str, agent_type: str) -> None:
        with self._lock:
            now = datetime.now(tz=timezone.utc)
            self._tasks[task_id] = TaskRecord(
                task_id=task_id,
                agent_type=agent_type,
                started_at=now,
                last_heartbeat=now,
            )

    def heartbeat(self, task_id: str, action_key: str = "") -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].last_heartbeat = datetime.now(tz=timezone.utc)
                if action_key:
                    self._tasks[task_id].action_key = action_key
                    self._action_history[action_key].append(time.time())

    def complete_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check_stalls()
            self._check_loops()
            time.sleep(30)

    def _check_stalls(self) -> None:
        now = datetime.now(tz=timezone.utc)
        with self._lock:
            for task_id, record in list(self._tasks.items()):
                elapsed = (now - record.last_heartbeat).total_seconds()
                if elapsed > STALL_TIMEOUT_SECONDS:
                    log.error(
                        "watchdog.stall_detected",
                        task_id=task_id,
                        agent=record.agent_type,
                        elapsed_seconds=elapsed,
                    )
                    # Mark for cancellation; orchestrator handles the actual kill
                    del self._tasks[task_id]

    def _check_loops(self) -> None:
        now = time.time()
        with self._lock:
            for action_key, timestamps in list(self._action_history.items()):
                recent = [t for t in timestamps if now - t < LOOP_WINDOW_SECONDS]
                self._action_history[action_key] = recent
                if len(recent) >= 5:
                    log.error(
                        "watchdog.loop_detected",
                        action_key=action_key,
                        occurrences=len(recent),
                    )


watchdog = AgentWatchdog()
