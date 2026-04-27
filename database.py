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
            )
            self._SessionFactory = sessionmaker(bind=self._engine)
            self.metadata.create_all(self._engine)
            logger.info("Database connection established successfully.")
        except SQLAlchemyError as e:
            logger.error("Failed to connect to database: %s", e)
            raise

    def disconnect(self) -> None:
        """Close the database connection pool."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database connection pool disposed.")

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around database operations."""
        if self._SessionFactory is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        session: Session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Database transaction failed: %s", e)
            raise
        finally:
            session.close()

    def upsert_stock_prices(self, records: List[Dict[str, Any]]) -> int:
        """
        Insert or update stock price records.

        Args:
            records: List of dicts with stock price data.

        Returns:
            Number of records processed.
        """
        if not records:
            return 0

        with self.session_scope() as session:
            for record in records:
                stmt = (
                    sqlalchemy.dialects.mysql.insert(self.stock_prices)
                    if "mysql" in self.config.connection_string
                    else text(
                        "INSERT INTO stock_prices (symbol, trade_date, open_price, "
                        "high_price, low_price, close_price, volume, turnover, change_pct) "
                        "VALUES (:symbol, :trade_date, :open_price, :high_price, "
                        ":low_price, :close_price, :volume, :turnover, :change_pct) "
                        "ON CONFLICT (symbol, trade_date) DO UPDATE SET "
                        "close_price = EXCLUDED.close_price, volume = EXCLUDED.volume"
                    )
                )
                session.execute(stmt, record)

        logger.debug("Upserted %d stock price records.", len(records))
        return len(records)

    def fetch_stock_prices(
        self, symbol: str, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve stock price records for a given symbol and date range.

        Args:
            symbol: Stock ticker symbol.
            start_date: Start date string in YYYY-MM-DD format.
            end_date: End date string in YYYY-MM-DD format.

        Returns:
            List of stock price record dicts.
        """
        query = text(
            "SELECT * FROM stock_prices "
            "WHERE symbol = :symbol "
            "AND trade_date BETWEEN :start_date AND :end_date "
            "ORDER BY trade_date ASC"
        )
        with self.session_scope() as session:
            result = session.execute(
                query,
                {"symbol": symbol, "start_date": start_date, "end_date": end_date},
            )
            return [dict(row._mapping) for row in result]
