import json
import re

def normalize_indicator_input(raw_value):
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
    Extracts the value associated with a given key from a dictionary. This is useful for lambda functions where we want to extract specific values from dictionaries in a DataFrame column.

    Args:
        dictionary (dict): The dictionary to extract the value from.
        key (str): The key whose value needs to be extracted. Defaults to 'database_id'.

    Returns:
        The value associated with the key if it exists, otherwise None.
    """
    if dictionary is not None and key in dictionary:
        return dictionary[key]
    return None