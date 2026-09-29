"""应用配置。

敏感值只从环境变量 / .env 读取，禁止硬编码、禁止打印、禁止写日志。
数据库连接用 SQLAlchemy URL.create() 构造，避免密码含特殊字符破坏 URI。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "liverno-acquisition-api"
    api_prefix: str = "/liver_api/v1"
    debug: bool = False

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "liverno_acquisition_dev"
    db_user: str = "acquisition_dev_user"
    db_password: str = ""

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 180.0

    @property
    def database_url(self) -> URL:
        """URL.create 会自行转义密码中的特殊字符。"""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
