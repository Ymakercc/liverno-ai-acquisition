"""测试夹具：使用独立测试库 schema，避免污染开发数据。"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base, get_db
from app.api.deps import get_strategy_generator
from app.generators.base import (
    GeneratedChannel,
    GeneratedQuery,
    GeneratedStrategy,
    StrategyGenerator,
)
from app.main import app

TEST_SCHEMA = "test_p0"


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    eng = create_engine(settings.database_url, future=True)
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
    eng.dispose()
    eng = create_engine(
        settings.database_url,
        future=True,
        connect_args={"options": f"-csearch_path={TEST_SCHEMA}"},
    )
    Base.metadata.create_all(eng)
    yield eng
    with eng.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
    eng.dispose()


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    session = Session()
    # 每个用例开始前清空业务表
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(text(f'TRUNCATE TABLE {TEST_SCHEMA}."{table.name}" CASCADE'))
    session.commit()
    yield session
    session.close()


class FakeGenerator(StrategyGenerator):
    """确定性假生成器，不调用真实 DeepSeek。"""

    def __init__(self, strategy: GeneratedStrategy | None = None, error: Exception | None = None):
        self.strategy = strategy
        self.error = error
        self.calls = 0

    def generate(self, profile):
        self.calls += 1
        if self.error:
            raise self.error
        if self.strategy:
            return self.strategy
        return GeneratedStrategy(
            channels=[
                GeneratedChannel(
                    channel="google",
                    enabled=True,
                    target_countries=["DE"],
                    strategy_summary="以行业词叠加国家做组合检索",
                    queries=[
                        GeneratedQuery(
                            query_text="industrial automation manufacturer Germany",
                            country_code="DE",
                            language="en",
                            enabled=True,
                            sort_order=0,
                        ),
                        GeneratedQuery(
                            query_text="Automatisierungstechnik Hersteller",
                            country_code="DE",
                            language="de",
                            enabled=True,
                            sort_order=1,
                        ),
                    ],
                )
            ]
        )


@pytest.fixture
def fake_generator():
    return FakeGenerator()


@pytest.fixture
def client(db_session, fake_generator):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_strategy_generator] = lambda: fake_generator
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def profile_payload(**overrides) -> dict:
    payload = {
        "profile_name": f"测试画像-{uuid.uuid4().hex[:6]}",
        "target_industries": ["industrial_automation"],
        "target_regions": ["western_europe"],
        "target_countries": ["DE"],
        "company_types": ["oem"],
        "company_size": "51-200",
        "product_lines": ["terminal_connector"],
        "application_scenarios": ["industrial_cabinet"],
        "required_signals": ["官网展示控制柜产品"],
        "exclude_signals": ["纯电商零售"],
        "target_roles": ["purchasing_manager"],
        "daily_quota": 60,
        "priority": "high",
        "is_enabled": True,
    }
    payload.update(overrides)
    return payload
