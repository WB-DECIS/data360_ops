import json
import re
import yaml
from pathlib import Path

def normalize_indicator_input(raw_value):
    """
    Normalize indicator input into a list of indicator identifiers.

    Accepts a JSON array (for example, from a ``for_each_task`` value) or a
    comma-separated string (for example, a job-level value). Surrounding
    whitespace and quote characters are removed from each identifier.

    Args:
        raw_value (str): Indicator input to normalize. Empty input is allowed.

    Returns:
        list[str]: A list of normalized indicator identifiers, or an empty
        list when ``raw_value`` is empty.
    """
    
    if not raw_value:
        return []

    raw_value = raw_value.strip()

    # Case 1: JSON array (from for_each_task)
    if raw_value.startswith("[") and raw_value.endswith("]"):
        try:
            values = json.loads(raw_value)
            return [str(v).strip().strip('"').strip("'") for v in values]
        except Exception:
            pass  # fall through

    # Case 2: Comma-separated string (job-level)
    parts = raw_value.split(",")

    return [
        re.sub(r'^[\'"]+|[\'"]+$', "", p.strip())
        for p in parts
        if p.strip()
    ]

# Extract value from a key in a dictionary 
def extract_value_from_key(dictionary, key='database_id'):
    """
    Extracts the value associated with a given key from a dictionary. 
    This is useful for lambda functions where we want to extract specific values
    from dictionaries in a DataFrame column.

    Args:
        dictionary (dict): The dictionary to extract the value from.
        key (str): The key whose value needs to be extracted. Defaults to 'database_id'.

    Returns:
        The value associated with the key if it exists, otherwise None.
    """
    if dictionary is not None and key in dictionary:
        return dictionary[key]
    return None


def load_global_yaml_config(env, filepath, section=None):
    """
    Loads a YAML configuration file from the global parameters path
    based on environment (Databricks or local).

    Args:
        env (dict): output of initialize_environment()
        filepath (str): full path to YAML file to load (e.g., '/path/to/util_params.yml')
        section (str, optional): key to extract from YAML file. 
                                 If None, returns full config.

    Returns:
        dict: config or specific section of the config
    """
    if env is None:
        raise ValueError("env parameter is required. Pass the output of initialize_environment().")

    if filepath is None:
            raise ValueError("filepath parameter is required.")

    # --- Build full YAML file path ---
    print(f"Using config path: {filepath}, section: {section}")

    if not Path(filepath).exists():
        raise FileNotFoundError(f"YAML file not found: {filepath}")

    # --- Load YAML content ---
    with open(filepath, "r") as f:
        config = yaml.safe_load(f)

    # --- Extract section if requested ---
    if section:
        if section not in config:
            raise KeyError(f"Section '{section}' not found in YAML file: {filepath}")
        return config[section]

    return config