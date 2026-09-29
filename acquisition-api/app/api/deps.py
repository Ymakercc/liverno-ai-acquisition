"""FastAPI 依赖。"""

from app.generators.base import StrategyGenerator
from app.generators.deepseek import DeepSeekStrategyGenerator


def get_strategy_generator() -> StrategyGenerator:
    """默认使用 DeepSeek；测试可通过依赖覆盖注入 Fake。"""
    return DeepSeekStrategyGenerator()
