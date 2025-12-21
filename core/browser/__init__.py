"""Browser automation module using Playwright CDP."""

from .browser_manager import BrowserManager
from .browser_actions import BrowserActionExecutor

__all__ = ["BrowserManager", "BrowserActionExecutor"]
