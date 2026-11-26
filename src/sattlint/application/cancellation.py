"""Cancel an analysis that runs in a child process.

The interactive shell runs an analysis in a short-lived child process. That
child forks its own analyzer pool, so stopping the run means stopping the whole
process tree: signalling only the child leaves the forked workers running and
keeps the child's stderr pipe open, which would block the parent's output
reader.

``AnalysisCancellation`` is the thread-safe switch the UI flips. It signals the
process group and returns immediately; a daemon watchdog escalates to a kill if
the tree does not stop within the grace period.
"""

from __future__ import annotations

import atexit
import os
import signal
import subprocess
import threading
from typing import Final, TypedDict

__all__ = [
    "AnalysisCancellation",
    "process_group_spawn_kwargs",
    "terminate_process_tree",
]

#: How long a graceful cancel may take before the watchdog kills the tree.
_CANCEL_GRACE_SECONDS: Final = 1.0

#: Every child process the app has launched and not yet reaped. The atexit hook
#: guarantees that quitting cannot leave an analysis running after the shell.
_live_processes: dict[int, subprocess.Popen[str]] = {}
_live_lock = threading.Lock()


class _SpawnKwargs(TypedDict, total=False):
    start_new_session: bool
    creationflags: int


class AnalysisCancellation:
    """A thread-safe cancel switch for an analysis running in a child process."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._watchdog: threading.Timer | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled.is_set()

    def cancel(self, *, force: bool = False) -> None:
        """Request cancellation without waiting for the child to exit.

        A graceful cancel sends ``SIGINT`` and lets the child report the run as
        cancelled. ``force=True`` kills the tree immediately; quitting uses it
        because nothing in flight is worth waiting for.
        """
        self._cancelled.set()
        process = self._attached_process()
        if process is None:
            return
        if force:
            terminate_process_tree(process, force=True)
            return
        terminate_process_tree(process, force=False)
        self._start_watchdog(process)

    def attach(self, process: subprocess.Popen[str]) -> None:
        """Track the child and kill it at once if cancellation came first."""
        with self._lock:
            self._process = process
            cancelled = self._cancelled.is_set()
        _track_process(process)
        if cancelled:
            terminate_process_tree(process, force=True)

    def detach(self, process: subprocess.Popen[str]) -> None:
        """Stop tracking a child that finished, or whose reader is closing."""
        with self._lock:
            if self._process is process:
                self._process = None
            watchdog = self._watchdog
            self._watchdog = None
        _untrack_process(process)
        if watchdog is not None:
            watchdog.cancel()

    def _attached_process(self) -> subprocess.Popen[str] | None:
        with self._lock:
            return self._process

    def _start_watchdog(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._watchdog is not None:
                return
            watchdog = threading.Timer(_CANCEL_GRACE_SECONDS, self._escalate, args=(process,))
            watchdog.daemon = True
            self._watchdog = watchdog
        watchdog.start()

    def _escalate(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._watchdog = None
        # The direct child may already be dead while a forked worker in its
        # process group is still alive; signal the group, not the pid status.
        terminate_process_tree(process, force=True)


def process_group_spawn_kwargs() -> _SpawnKwargs:
    """``Popen`` options that put the child in its own process group."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def terminate_process_tree(process: subprocess.Popen[str], *, force: bool) -> None:
    """Signal the child and every process it forked.

    The signal goes to the process group even when the direct child has already
    exited: a forked analyzer worker may still be running in that group and may
    still hold the parent's stderr pipe open.
    """
    if os.name == "nt":
        _terminate_windows_tree(process, force=force)
        return
    # ``start_new_session`` made the child the leader of its own session, so its
    # pid is also the process-group id shared by its forked analyzer workers.
    if force:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            _send_signal(process, signal.SIGKILL)
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
    except OSError:
        _send_signal(process, signal.SIGINT)


def _send_signal(process: subprocess.Popen[str], sig: int) -> None:
    try:
        process.send_signal(sig)
    except (OSError, ValueError):
        return


def _terminate_windows_tree(process: subprocess.Popen[str], *, force: bool) -> None:
    command = ["taskkill", "/T", "/PID", str(process.pid)]
    if force:
        command.insert(1, "/F")
    try:
        subprocess.run(command, check=False, capture_output=True)
    except OSError:
        if force:
            process.kill()
        else:
            process.terminate()


def _track_process(process: subprocess.Popen[str]) -> None:
    with _live_lock:
        _live_processes[process.pid] = process


def _untrack_process(process: subprocess.Popen[str]) -> None:
    with _live_lock:
        _live_processes.pop(process.pid, None)


@atexit.register
def _stop_tracked_processes() -> None:
    with _live_lock:
        processes = tuple(_live_processes.values())
        _live_processes.clear()
    # Signal every tracked group even when the direct child is already gone:
    # a surviving forked worker is the case this safety net exists for.
    for process in processes:
        terminate_process_tree(process, force=True)
