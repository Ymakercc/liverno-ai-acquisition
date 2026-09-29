"""人类可读编号生成（PRF-0001 / STG-0001）。

用表内最大序号 +1，简单够用；并发冲突由唯一约束兜底，调用方重试即可。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_code(db: Session, model, prefix: str, width: int = 4) -> str:
    total = db.scalar(select(func.count()).select_from(model)) or 0
    return f"{prefix}-{total + 1:0{width}d}"
