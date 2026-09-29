"""统一业务异常。

前端 request.ts 约定：
  成功  -> HTTP 2xx + {code: 0, message, data}
  失败  -> HTTP 4xx/5xx + {code: "<业务码>", message}
业务层通过 code 判断场景，不做 message 文本匹配。
"""


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "BUSINESS_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, status_code=404, code="NOT_FOUND")


class ConflictError(AppError):
    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(message, status_code=409, code=code)


class ValidationError(AppError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message, status_code=400, code=code)


# ---------- 业务错误码（与前端常量保持一致） ----------
STRATEGY_VERSION_CONFLICT = "STRATEGY_VERSION_CONFLICT"
PROFILE_NAME_DUPLICATED = "PROFILE_NAME_DUPLICATED"
STRATEGY_NOT_ACTIVATABLE = "STRATEGY_NOT_ACTIVATABLE"
AI_GENERATION_FAILED = "AI_GENERATION_FAILED"
