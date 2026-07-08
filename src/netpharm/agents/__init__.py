"""Ordered registry of pipeline agents.

The orchestrator consumes AGENT_SEQUENCE to build the LangGraph. Order here IS
the pipeline order; each agent's output table feeds the next.
"""
from .adme import AdmeAgent
from .base import AgentError, BaseAgent
from .cytoscape import CytoscapeAgent
from .disease import DiseaseAgent
from .enrichment import EnrichmentAgent
from .extractor import ExtractorAgent
from .hubgenes import HubGeneAgent
from .intersection import IntersectionAgent
from .ppi import PpiAgent
from .report import ReportAgent
from .standardize import StandardizeAgent
from .targets import TargetsAgent

AGENT_SEQUENCE: list[type[BaseAgent]] = [
    ExtractorAgent,       # 1
    StandardizeAgent,     # 2
    AdmeAgent,            # 3
    TargetsAgent,         # 4
    DiseaseAgent,         # 5
    IntersectionAgent,    # 6
    PpiAgent,             # 7
    EnrichmentAgent,      # 8
    HubGeneAgent,         # 10 (hub ranking before Cytoscape so hubs can be styled)
    CytoscapeAgent,       # 9
    ReportAgent,          # 11
]

__all__ = ["AGENT_SEQUENCE", "AgentError", "BaseAgent"]
