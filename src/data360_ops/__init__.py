# read version from installed package
from importlib.metadata import version
from .github import create_issues_for_dataset

__version__ = version("data360_ops")
__all__ = ["create_issues_for_dataset"]