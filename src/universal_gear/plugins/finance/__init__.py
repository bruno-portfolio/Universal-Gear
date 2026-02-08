"""Finance domain plugin -- Brazilian macroeconomic intelligence via BCB APIs.

Importing this package triggers decorator-based registration of all six stages.
"""

from universal_gear.plugins.finance.action import FinanceActionEmitter
from universal_gear.plugins.finance.analyzer import FinanceAnalyzer
from universal_gear.plugins.finance.collector import BCBCollector
from universal_gear.plugins.finance.model import FinanceScenarioEngine
from universal_gear.plugins.finance.monitor import FinanceMonitor
from universal_gear.plugins.finance.processor import FinanceProcessor

__all__ = [
    "BCBCollector",
    "FinanceActionEmitter",
    "FinanceAnalyzer",
    "FinanceMonitor",
    "FinanceProcessor",
    "FinanceScenarioEngine",
]
