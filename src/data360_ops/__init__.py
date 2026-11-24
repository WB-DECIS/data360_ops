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
    filter_projects_by_changed_date,
    create_metadata_project_indicator,
	create_metadata_project_database,
	get_exist_meta_id_across_collections,
    find_dataset_collection,
    find_collection_exact,
    create_collection,
    grant_admin_access,
    add_projects_to_collection,
    move_collection_to_another_collection,
    get_meta_by_dataset_db,
    get_meta_by_dataset_db_across_collections,
    update_patch
)

from .utils import load_global_yaml_config

__version__ = version("data360_ops")
__all__ = [
    "create_issues_for_dataset",
    "load_token",
    "get_token_with_username",
    "download_file",
    "list_files",
    "get_projects_from_collection",
    "filter_projects_by_changed_date",
    "create_metadata_project_indicator",
    "create_metadata_project_database",
    "get_exist_meta_id_across_collections",
    "find_dataset_collection",
    "find_collection_exact",
    "create_collection",
    "grant_admin_access",
    "add_projects_to_collection",
    "move_collection_to_another_collection",
    "load_global_yaml_config",
    "get_meta_by_dataset_db",
    "get_meta_by_dataset_db_across_collections",
    "update_patch"
]