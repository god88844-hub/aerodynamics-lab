"""Cooperative time limit scoped to one numerical run."""

from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic


class SimulationTimeLimit(RuntimeError):
    """Raised at a numerical checkpoint when the run's time is exhausted."""


class SimulationWorkLimit(ValueError):
    """The indicated run exceeds its numerical work allowance."""


_deadline: ContextVar[float | None] = ContextVar("simulation_deadline", default=None)


@contextmanager
def time_limit(seconds: float):
    deadline = monotonic() + seconds
    previous = _deadline.get()
    token = _deadline.set(deadline if previous is None else min(deadline, previous))
    try:
        yield
    finally:
        _deadline.reset(token)


def check_time_limit() -> None:
    deadline = _deadline.get()
    if deadline is not None and monotonic() >= deadline:
        raise SimulationTimeLimit("Simulation stopped at its execution time limit.")
