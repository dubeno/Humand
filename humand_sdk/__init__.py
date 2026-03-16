"""
Humand SDK - Universal Human-in-the-Loop Approval System
========================================================

A professional SDK for integrating human approval workflows into any Python application.
Works with AI frameworks like LangGraph, LangChain, or any custom workflow system.

Basic Usage:
    >>> from humand_sdk import require_approval, HumandClient
    >>> 
    >>> client = HumandClient(server_url="http://localhost:8000")
    >>> 
    >>> @require_approval(
    ...     title="Delete User Data",
    ...     approvers=["manager@company.com"],
    ...     client=client
    ... )
    ... def delete_user_data(user_id: str):
    ...     # This function will require approval before execution
    ...     return delete_data(user_id)

Framework Integration Examples:
    - LangGraph: Use with workflow nodes
    - LangChain: Integrate with custom tools
    - FastAPI: Add approval to API endpoints
    - Any Python function: Use the @require_approval decorator
"""

__version__ = "0.1.0"
__author__ = "Humand Team"
__email__ = "support@humand.io"

# Core imports
from .client import HumandClient
from .decorators import require_approval, ApprovalRequired
from .exceptions import (
    HumandError,
    ApprovalRejected,
    ApprovalTimeout,
    ConfigurationError,
    APIError
)

# Framework integrations are available in separate modules
# Example: agent_app/integrations/ contains LangGraph, LangChain integrations

# Configuration helpers
from .config import ApprovalConfig, NotificationConfig

__all__ = [
    # Core
    "HumandClient",
    "require_approval", 
    "ApprovalRequired",
    
    # Configuration
    "ApprovalConfig",
    "NotificationConfig",
    
    # Exceptions
    "HumandError",
    "ApprovalRejected", 
    "ApprovalTimeout",
    "ConfigurationError",
    "APIError",
    
    # Metadata
    "__version__",
]
