"""Email-first housing monitoring package.

This package keeps the reusable domain model and helper utilities in the top-level
package while treating the email ingestion flow as the primary application.
"""

from .models import Property, SearchCriteria

__all__ = ["Property", "SearchCriteria"]
