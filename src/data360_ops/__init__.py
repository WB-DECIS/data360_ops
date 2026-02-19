# read version from installed package
from importlib.metadata import version
from .github import create_issues_for_dataset, load_token
from .one_drive import (
    get_token_with_username,
    download_file,
    list_files
)
from .metadata_editor import (
    get_projects_from_collection, 
    filter_projects_by_changed_date
)

__version__ = version("data360_ops")
__all__ = [
    "create_issues_for_dataset",
    "load_token",
    "get_token_with_username",
    "download_file",
    "list_files",
    "get_projects_from_collection",
    "filter_projects_by_changed_date"
]