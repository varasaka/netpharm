"""Network Pharmacology multi-agent platform."""
from .config import Config
from .orchestrator import run_pipeline, run_single

__version__ = "0.1.0"
__all__ = ["Config", "run_pipeline", "run_single"]
