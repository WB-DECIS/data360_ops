# read version from installed package
from importlib.metadata import version
from .github import create_issues_for_dataset, load_token
from .one_drive import (
    get_token_with_username,
    download_file,
    list_files
)
from .ddh import (
    trigger_update
)
from .metadata_editor import (
    get_projects_from_collection,
    filter_projects_by_changed_date,
    get_exist_meta_id,
    get_exist_meta_id_across_collections,
    get_meta_by_dataset_db,
    get_meta_by_dataset_db_across_collections,
    update_project,
    create_project,
    check_geo_unit,
    update_patch,
    add_data360_admin_metadata,
    add_project_to_collection,
    manage_collection_projects,
    clean_admin_metadata,
    fetch_and_save,
    export_object,
    export_metadata_all,
    export_all_metadata,
    gen_metadata_information,
    gen_series_description,
    gen_database_description,
    gen_metadata_payloads,
    gen_metadata_payloads_database,
    gen_metadata_patch,
    gen_metadata_patch_database,
    create_edit_metadata_project_indicator,
    create_edit_metadata_project_database,
    create_metadata_project_indicator,
    create_metadata_project_database,
    update_metadata_project_indicator,
    update_metadata_project_database,
    find_dataset_collection,
    find_collection_exact,
    create_collection,
    grant_admin_access,
    add_projects_to_collection,
    move_collection_to_another_collection,
    _export_file,
    export_metadata_db
)

from .fmr import (
    get_codelist_pairs,
    extract_validation_info,
    extract_schema_summary,
    build_lookup_dict,
    get_dimensions_with_lookup_dict
)
from .utils import (
    load_global_yaml_config,
    build_indicator_metadata_summary,
    build_indicator_metadata_summary_spark,
    build_database_metadata_summary
)

__version__ = version("data360_ops")
__all__ = [
    "get_token_with_username",
    "download_file",
    "list_files",
    "load_global_yaml_config",
    "get_projects_from_collection",
    "filter_projects_by_changed_date",
    "get_exist_meta_id",
    "get_exist_meta_id_across_collections",
    "get_meta_by_dataset_db",
    "get_meta_by_dataset_db_across_collections",
    "update_project",
    "create_project",
    "check_geo_unit",
    "update_patch",
    "add_data360_admin_metadata",
    "add_project_to_collection",
    "manage_collection_projects",
    "clean_admin_metadata",
    "fetch_and_save",
    "export_object",
    "export_metadata_all",
    "export_all_metadata",
    "gen_metadata_information",
    "gen_series_description",
    "gen_database_description",
    "gen_metadata_payloads",
    "gen_metadata_payloads_database",
    "gen_metadata_patch",
    "gen_metadata_patch_database",
    "create_edit_metadata_project_indicator",
    "create_edit_metadata_project_database",
    "create_metadata_project_indicator",
    "create_metadata_project_database",
    "update_metadata_project_indicator",
    "update_metadata_project_database",
    "find_dataset_collection",
    "find_collection_exact",
    "create_collection",
    "grant_admin_access",
    "add_projects_to_collection",
    "move_collection_to_another_collection",
    "get_codelist_pairs",
    "extract_validation_info",
    "extract_schema_summary",
    "build_lookup_dict",
    "get_dimensions_with_lookup_dict",
    "build_indicator_metadata_summary",
    "build_indicator_metadata_summary_spark",
    "build_database_metadata_summary",
    "trigger_update",
    "_export_file",
    "export_metadata_db"
]