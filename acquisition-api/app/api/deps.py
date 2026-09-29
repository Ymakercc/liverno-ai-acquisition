"""FastAPI 依赖。"""

from app.generators.base import StrategyGenerator
from app.generators.deepseek import DeepSeekStrategyGenerator
from app.providers.base import SearchProvider
from app.providers.serper import SerperSearchProvider


def get_strategy_generator() -> StrategyGenerator:
    """默认使用 DeepSeek；测试可通过依赖覆盖注入 Fake。"""
    return DeepSeekStrategyGenerator()


def get_search_provider() -> SearchProvider:
    """Session B1 只接一个真实搜索渠道：Serper Google Search。"""
    return SerperSearchProvider()
