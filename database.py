"""Database connection and operations module for daily stock analysis."""

import logging
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

import sqlalchemy
from sqlalchemy import create_engine, text, MetaData, Table, Column
from sqlalchemy import Integer, String, Float, Date, DateTime, BigInteger
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from config import DatabaseConfig

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and stock data persistence."""

    def __init__(self, config: DatabaseConfig):
        """
        Initialize the database manager.

        Args:
            config: DatabaseConfig instance with connection settings.
        """
        self.config = config
        self._engine: Optional[sqlalchemy.engine.Engine] = None
        self._SessionFactory: Optional[sessionmaker] = None
        self.metadata = MetaData()
        self._define_tables()

    def _define_tables(self) -> None:
        """Define the database schema tables."""
        self.stock_prices = Table(
            "stock_prices",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False, index=True),
            Column("trade_date", Date, nullable=False, index=True),
            Column("open_price", Float),
            Column("high_price", Float),
            Column("low_price", Float),
            Column("close_price", Float),
            Column("volume", BigInteger),
            Column("turnover", Float),
            Column("change_pct", Float),
        )

        self.analysis_results = Table(
            "analysis_results",
            self.metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("symbol", String(20), nullable=False, index=True),
            Column("analysis_date", Date, nullable=False, index=True),
            Column("indicator", String(50), nullable=False),
            Column("value", Float),
            Column("signal", String(20)),
            Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
        )

    def connect(self) -> None:
        """Establish database connection and create tables if needed."""
        try:
            self._engine = create_engine(
                self.config.connection_string,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                echo=self.config.echo_sql,
                # Added pool_pre_ping to avoid stale connections after long idle periods
                pool_pre_ping=True,
            )
            self._SessionFactory = sessionmaker(bind=self._engine)
            self.metadata.create_all(self._engine)
            logger.info("Database connection established successfully.")
        except SQLAlchemyError as e:
            logger.error("Failed to connect to database: %s", e)
            raise

    def disconnect(self)
