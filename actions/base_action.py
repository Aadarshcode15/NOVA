# actions/base_action.py
# Base class for all Sprint 3+ action modules.
# Provides: automatic retry, structured results, error handling, logging.

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from core.logger import log


@dataclass
class ActionResult:
    """Structured return type for all action handlers."""
    success: bool
    message: str                          # spoken to user via TTS
    data:    dict = field(default_factory=dict)   # structured payload for future UI use


class BaseAction(ABC):
    """
    Inherit from this to get retry logic, error handling,
    and consistent logging for free.

    Subclass pattern:
        class CalendarAction(BaseAction):
            def can_handle(self, command, intent): ...
            def execute(self, command, context) -> ActionResult: ...
    """

    MAX_RETRIES  = 2
    RETRY_DELAY  = 1.5    # seconds between retries (multiplied by attempt number)

    # ── Subclasses implement these two ────────────────────

    @abstractmethod
    def can_handle(self, command: str, intent: dict) -> bool:
        """Return True if this action should handle this command."""
        ...

    @abstractmethod
    def execute(self, command: str, context: dict) -> ActionResult:
        """
        Do the actual work. Raise exceptions freely —
        the handle() wrapper catches and retries them.
        """
        ...

    # ── Public entry point ────────────────────────────────

    def handle(self, command: str, context: dict = None) -> bool:
        """
        Call this from the router.
        Retries up to MAX_RETRIES times on exception.
        Speaks result.message on success, fallback message on total failure.
        Returns True if handled (success or graceful failure), False to pass through.
        """
        from core.voice import speak
        ctx = context or {}

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                result = self.execute(command, ctx)
                if result.message:
                    speak(result.message)
                return result.success

            except _AuthRequired as e:
                # Auth errors should never retry — surface immediately
                log.error(f"[{self.__class__.__name__}] Auth required: {e}")
                speak(str(e))
                return True    # handled — just needs setup

            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    wait = self.RETRY_DELAY * (attempt + 1)
                    log.warning(
                        f"[{self.__class__.__name__}] "
                        f"Attempt {attempt + 1}/{self.MAX_RETRIES + 1} failed: {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    time.sleep(wait)
                else:
                    log.error(
                        f"[{self.__class__.__name__}] "
                        f"Failed after {self.MAX_RETRIES + 1} attempts: {e}"
                    )
                    speak("Sorry, that didn't work. Please try again in a moment.")
                    return True   # handled (with failure) — don't fall to AI

        return True


class _AuthRequired(Exception):
    """Raised when OAuth credentials are missing or invalid."""
    pass