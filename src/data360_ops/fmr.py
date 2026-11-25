# In this module, I pasted sections 1 and 2 from publishing.py script developed by Echo
import pandas as pd

def get_codelist_pairs(comp, coded_comp):
    """
    Retrieve all codelist code-label pairs for given coded components.

    Args:
        comp (list): List of components.
        coded_comp (list): List of coded components.

    Returns:
        dict: Dictionary with coded components as keys and list of (code, label) pairs as values.
    """
    codelist_dict = {}
    for component in coded_comp:
        codes = comp[component].local_codes.items
        codelist_dict[component] = [
            (code.id, getattr(code, "name", code.id))  # fallback to id if name missing
            for code in codes
        ]
    return codelist_dict

def extract_validation_info(schema):
    """
    Extract validation information from a given schema, including code-label pairs.

    Args:
        schema: The schema object containing validation information.

    Returns:
        dict: A dictionary containing validation information:
            - valid_comp: List of valid component names.
            - mandatory_comp: List of mandatory component names.
            - coded_comp: List of coded component names.
            - codelists: Dictionary with coded components as keys and list of (code, label) pairs.
            - dim_comp: List of dimension component names.
    """
    comp = schema.components
    coded = [c.id for c in comp if comp[c.id].local_codes is not None]

    validation_info = {
        "valid_comp": [c.id for c in comp],
        "mandatory_comp": [c.id for c in comp if comp[c.id].required],
        "coded_comp": coded,
        "codelists": get_codelist_pairs(comp, coded),
        "dim_comp": [c.id for c in comp if comp[c.id].role == px.model.Role.DIMENSION],
    }
    return validation_info

def extract_schema_summary(schema):
    """
    Extract schema summary from parsed pickle file.
    
    Returns a dict with:
      - dim_comp: list of component IDs that are DIMENSIONS
      - components: DataFrame with component details
    """
    rows = []

    for comp in schema.components.data:
        row = {
            "component_id": comp.id,
            "component_name": comp.name,
            "role": getattr(comp.role, "name", None),  # DIMENSION, ATTRIBUTE, etc.
            "required": getattr(comp, "required", False),
            "codelist_id": getattr(comp.local_codes, "id", None) if comp.local_codes else None,
            "codelist_name": getattr(comp.local_codes, "name", None) if comp.local_codes else None
        }
        rows.append(row)

    return pd.DataFrame(rows)

def build_lookup_dict(validation_info):
    """
    Convert validation_info['codelists'] into nested dicts for easy mapping.
    Example: { "REF_AREA": {"AFG": "Afghanistan", "WLD": "World"}, ... }
    """
    lookup = {}
    for comp, pairs in validation_info["codelists"].items():
        lookup[comp] = {code: label for code, label in pairs}
    return lookup

def get_dimensions_with_lookup_dict(df, schema_summary, lookup_dict):
    """
    Extract dimensions covered by each indicator based on schema summary df.
    Logic:
      - Only include components with role == "DIMENSION" (from schema_summary)
      - Use component_name for labels
      - "FREQ", "INDICATOR", "OBS_VALUE" are skipped
      - Special handling for REF_AREA, SEX, URBANISATION, AGE
      - COMP_BREAKDOWN_* columns map codes using lookup_dict and extract human-readable dimension label
    """
    # Only DIMENSION components
    dim_list = schema_summary.loc[schema_summary["role"] == "DIMENSION", "component_id"].values

    # Only consider rows with non-null OBS_VALUE
    df_valid = df[df["OBS_VALUE"].notna()]

    indicator_dimension = {}

    for ind, subdf in df_valid.groupby("INDICATOR"):
        values = set()

        for dim in dim_list:
            # Skip non-breakdown columns
            if dim in ["INDICATOR", "OBS_VALUE", "FREQ", "UNIT_MEASURE"]:
                continue

            # Special handling for certain dimensions
            if dim == "REF_AREA":
                values.add(("Geographic area", "Country/economy, Region"))
                continue
            elif dim == "SEX":
                unique_vals = df["SEX"].dropna().unique()
                if len(unique_vals) > 1:
                    values.add(("Sex", "Total, Male, Female"))
                continue

            elif dim == "URBANISATION":
                unique_vals = df["URBANISATION"].dropna().unique()
                if len(unique_vals) > 1:
                    values.add(("Residential area", "Total, Urban, Rural"))
                continue

            elif dim == "AGE":
                unique_vals = df["AGE"].dropna().unique()
                if len(unique_vals) > 1:
                    values.add(("Age", ""))
                continue

            # Handle COMP_BREAKDOWN_* columns if present
            comp_breakdown_cols = [c for c in ["COMP_BREAKDOWN_1", "COMP_BREAKDOWN_2", "COMP_BREAKDOWN_3"] if c in subdf.columns]
            if comp_breakdown_cols:
                for col in comp_breakdown_cols:
                    # Flatten and get unique codes
                    codes = subdf[col].explode().unique() if subdf[col].apply(lambda x: isinstance(x, list)).any() else subdf[col].unique()
                    for code in codes:
                        if code in ["_T", "_Z"]:
                            continue
                        # Map code to human-readable value using codelist for that column
                        mapped_value = lookup_dict.get(col, {}).get(code, code)
                        # Extract dimension label (part before ":" if present)
                        dimension_label = mapped_value.split(":")[0].strip() if ":" in mapped_value else mapped_value
                        values.add((dimension_label, ""))

            else:
                # Fallback: use component_name from schema_summary
                comp_name = schema_summary.loc[schema_summary["component_id"] == dim, "component_name"].values
                if len(comp_name) > 0:
                    values.add((comp_name[0], ""))  # Use human-readable name

        # UNIT_MEASURE as dimension when the indicator has multiple units of measure
        if "UNIT_MEASURE" in subdf.columns:
            um_codes = subdf["UNIT_MEASURE"].dropna().unique()
            if len(um_codes) > 1:
                translated = sorted([
                    lookup_dict.get("UNIT_MEASURE", {}).get(u, u)
                    for u in um_codes
                ])
                values.add(("Unit of measure", ", ".join(translated)))

        # Build final list of dicts
        indicator_dimension[ind] = [
            {"label": v[0]} if v[1] == "" else {"label": v[0], "description": v[1]}
            for v in values
        ]

    return indicator_dimension
