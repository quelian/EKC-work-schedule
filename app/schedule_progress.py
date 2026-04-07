"""Потокобезопасное состояние прогресса построения графика для SSE."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_store: dict[str, dict[str, Any]] = {}


def get_progress_snapshot(session_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _store.get(session_id)
        return dict(row) if row else None


def forget_progress(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)


def _put(session_id: str, payload: dict[str, Any]) -> None:
    with _lock:
        _store[session_id] = payload


class ScheduleProgressReporter:
    """Обновляет снимок для GET /schedule/progress/stream/{id} из потока построения."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        # Число шагов после done() выставит 100%; до этого вызываем next() столько раз, сколько этапов.
        self.total = 10
        self._step = 0
        self._start = time.monotonic()
        self._phase = ""

    def _eta_seconds(self) -> int:
        elapsed = max(0.001, time.monotonic() - self._start)
        rate = elapsed / max(self._step, 1)
        remaining = max(0, self.total - self._step)
        return int(max(8, min(3600, remaining * max(rate, 4.0))))

    def _write(
        self,
        *,
        phase: str,
        detail: str = "",
        step: int | None = None,
        finished: bool = False,
        error: str | None = None,
    ) -> None:
        self._phase = phase
        if step is not None:
            self._step = min(max(step, 0), self.total)
        if finished:
            self._step = self.total
        elapsed = int(time.monotonic() - self._start)
        pct = 100 if finished else min(98, int(100 * self._step / max(self.total, 1)))
        _put(
            self.session_id,
            {
                "phase": phase,
                "detail": detail,
                "step": self._step,
                "total": self.total,
                "percent": pct,
                "elapsed_sec": elapsed,
                "eta_sec": 0 if finished else self._eta_seconds(),
                "finished": finished,
                "error": error,
            },
        )

    def start(self) -> None:
        self._step = 0
        self._write(phase="Старт", detail="Принимаем запрос и готовим расчёт…", step=0)

    def next(self, phase: str, detail: str = "") -> None:
        self._step = min(self._step + 1, self.total)
        self._write(phase=phase, detail=detail, step=self._step)

    def set_step(self, step: int, phase: str, detail: str = "") -> None:
        self._write(phase=phase, detail=detail, step=step)

    def detail(self, detail: str) -> None:
        self._write(phase=self._phase, detail=detail, step=self._step)

    def done(self) -> None:
        self._write(phase="Готово", detail="Формируем страницу с результатом…", finished=True)

    def fail(self, message: str) -> None:
        self._write(phase="Ошибка", detail=message, finished=True, error=message)
