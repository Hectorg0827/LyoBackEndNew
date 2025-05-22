"""
Test configuration and fixtures.
"""
import os
import sys
import asyncio
import pytest
from typing import AsyncGenerator, Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool
from redis.asyncio import Redis

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.core.config import settings
from api.db.sql import get_db, init_db
from api.db.redis import initialize_redis, redis_client, get_redis
from main import app as main_app


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an event loop for the test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_app() -> Generator:
    """
    Create a FastAPI test application.
    """
    # Here we could add test-specific settings
    yield main_app


@pytest.fixture(scope="function")
def client(test_app: FastAPI) -> Generator:
    """
    Create a test client for FastAPI application.
    """
    with TestClient(test_app) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator:
    """
    Set up an in-memory database for testing.
    """
    # Create an in-memory SQLite database for testing
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    SQLModel.metadata.create_all(test_engine)
    
    # Override the get_db dependency
    async def get_test_db():
        session = Session(test_engine)
        try:
            yield session
        finally:
            session.close()
    
    # Temporarily replace the dependency
    main_app.dependency_overrides[get_db] = get_test_db
    
    yield
    
    # Remove the override
    main_app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
async def setup_test_redis() -> AsyncGenerator:
    """
    Set up a Redis mock for testing.
    """
    # Create a mock Redis client
    mock_redis = Redis.from_url("redis://localhost:6379/1")
    
    # Override the get_redis dependency
    async def get_test_redis():
        return mock_redis
        
    # Temporarily replace the dependency
    main_app.dependency_overrides[get_redis] = get_test_redis
    
    # Flush the test database before testing
    await mock_redis.flushdb()
    
    yield
    
    # Clean up
    await mock_redis.close()
    main_app.dependency_overrides.clear()
