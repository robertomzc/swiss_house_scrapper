"""Run the ImmoScout24 email -> JSON pipeline (manual run).

Usage: set env EMAIL_USER and EMAIL_PASSWORD (or use .env loader), then:
    python run_pipeline.py
"""
from __future__ import annotations

from housing_monitor.pipeline import main


if __name__ == '__main__':
    main()
