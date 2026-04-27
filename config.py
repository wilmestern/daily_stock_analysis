"""Configuration management for daily stock analysis.

Loads and validates environment variables and application settings.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "stock_analysis"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def connection_string(self) -> str:
        """Return a formatted database connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class StockConfig:
    """Stock data fetching configuration."""
    # Default list of stock symbols to analyze
    default_symbols: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in os.getenv("STOCK_SYMBOLS", "AAPL,GOOGL,MSFT,AMZN,TSLA").split(",")
            if s.strip()
        ]
    )
    # Data source API key
    api_key: str = field(default_factory=lambda: os.getenv("STOCK_API_KEY", ""))
    # API provider: 'yfinance', 'alpha_vantage', 'polygon'
    api_provider: str = field(default_factory=lambda: os.getenv("STOCK_API_PROVIDER", "yfinance"))
    # Request timeout in seconds
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("STOCK_REQUEST_TIMEOUT", "30"))
    )
    # Number of retry attempts on failure
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("STOCK_MAX_RETRIES", "3"))
    )


@dataclass
class AnalysisConfig:
    """Analysis parameters configuration."""
    # Moving average windows (in days)
    ma_short_window: int = field(
        default_factory=lambda: int(os.getenv("MA_SHORT_WINDOW", "5"))
    )
    ma_long_window: int = field(
        default_factory=lambda: int(os.getenv("MA_LONG_WINDOW", "20"))
    )
    # RSI period
    rsi_period: int = field(
        default_factory=lambda: int(os.getenv("RSI_PERIOD", "14"))
    )
    # Bollinger Bands standard deviation multiplier
    bb_std_dev: float = field(
        default_factory=lambda: float(os.getenv("BB_STD_DEV", "2.0"))
    )
    # Minimum volume threshold for valid trading signals
    min_volume_threshold: int = field(
        default_factory=lambda: int(os.getenv("MIN_VOLUME_THRESHOLD", "100000"))
    )


@dataclass
class OutputConfig:
    """Output and reporting configuration."""
    output_dir: str = field(default_factory=lambda: os.getenv("OUTPUT_DIR", "output"))
    report_format: str = field(default_factory=lambda: os.getenv("REPORT_FORMAT", "html"))
    save_charts: bool = field(
        default_factory=lambda: os.getenv("SAVE_CHARTS", "true").lower() == "true"
    )
    chart_dpi: int = field(default_factory=lambda: int(os.getenv("CHART_DPI", "150")))
    email_enabled: bool = field(
        default_factory=lambda: os.getenv("EMAIL_ENABLED", "false").lower() == "true"
    )
    email_recipients: List[str] = field(
        default_factory=lambda: [
            r.strip()
            for r in os.getenv("EMAIL_RECIPIENTS", "").split(",")
            if r.strip()
        ]
    )


@dataclass
class AppConfig:
    """Top-level application configuration aggregating all sub-configs."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    stock: StockConfig = field(default_factory=StockConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )

    def validate(self) -> None:
        """Validate critical configuration values and raise errors for missing required fields."""
        if self.stock.api_provider not in ("yfinance", "alpha_vantage", "polygon"):
            raise ValueError(
                f"Unsupported API provider: '{self.stock.api_provider}'. "
                "Choose from: yfinance, alpha_vantage, polygon"
            )
        if self.stock.api_provider != "yfinance" and not self.stock.api_key:
            raise ValueError(
                f"STOCK_API_KEY is required when using provider '{self.stock.api_provider}'"
            )
        if self.analysis.ma_short_window >= self.analysis.ma_long_window:
            raise ValueError(
                "MA_SHORT_WINDOW must be less than MA_LONG_WINDOW"
            )
        if self.output.report_format not in ("html", "pdf", "csv", "json"):
            raise ValueError(
                f"Unsupported report format: '{self.output.report_format}'. "
                "Choose from: html, pdf, csv, json"
            )


# Module-level singleton for convenient import
config = AppConfig()
