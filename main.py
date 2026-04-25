#!/usr/bin/env python3
"""
Daily Stock Analysis - Main Entry Point

This module serves as the primary entry point for the daily stock analysis tool.
It orchestrates data fetching, analysis, and report generation.
"""

import os
import sys
import logging
import argparse
from datetime import datetime, date
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"logs/analysis_{date.today().strftime('%Y%m%d')}.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments for the analysis tool."""
    parser = argparse.ArgumentParser(
        description="Daily Stock Analysis Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --symbols AAPL TSLA MSFT
  python main.py --symbols AAPL --date 2024-01-15
  python main.py --config config/stocks.json --output reports/
        """,
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        type=str,
        help="Stock ticker symbols to analyze (e.g., AAPL TSLA MSFT)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=date.today().strftime("%Y-%m-%d"),
        help="Analysis date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=os.getenv("STOCK_CONFIG_PATH", "config/stocks.json"),
        help="Path to stock configuration file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getenv("REPORT_OUTPUT_DIR", "reports/"),
        help="Directory to save analysis reports",
    )
    # Changed default to True so I always get detailed logs during personal use
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Enable verbose/debug logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run analysis without saving reports",
    )

    return parser.parse_args()


def setup_directories(output_dir: str) -> None:
    """Ensure required directories exist before running analysis."""
    directories = [output_dir, "logs", "data/cache"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug("Ensured directory exists: %s", directory)


def validate_date(date_str: str) -> Optional[date]:
    """Validate and parse the provided date string."""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
        if parsed > date.today():
            logger.warning("Analysis date %s is in the future; results may be incomplete.", date_str)
        return parsed
