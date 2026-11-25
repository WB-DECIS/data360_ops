import json
import re
import yaml
from pathlib import Path
import pandas as pd
from .fmr import get_dimensions_with_lookup_dict
from pyspark.sql import functions as F

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

def build_indicator_metadata_summary(df, schema, env, lookup_dict, schema_summary, country_codes):
    """
    Build metadata summary table with correct REF_COUNTRY and cleaned UNIT_MEASURE.

    Args:
        df (pd.DataFrame): Raw SDMX-style data with coded columns.
        validation_info (dict): Info containing codelists for translation.
        env: Environment for fetching country codes.

    Returns:
        pd.DataFrame: Metadata summary table.
    """
    # Get dimension
    dimensions_dict = get_dimensions_with_lookup_dict(df, schema_summary, lookup_dict)
    
    # Group by original codes
    id_column = None
    for col in ["DATABASE_ID", "DATASET_ID"]:
        if col in df.columns:
            id_column = col
            break

    if id_column is None:
        raise ValueError("Neither 'DATABASE_ID' nor 'DATASET_ID' found in DataFrame columns.")

    # Dynamically build group columns
    group_cols = [id_column, "INDICATOR"]
    summary_rows = []

    for (db_code, ind_code), group in df.groupby(group_cols):
        row = {
            id_column: db_code,
            "INDICATOR": ind_code
        }

        # UNIT_MEASURE aggregation — composite UNIT_MULT + UNIT_MEASURE labels
        if "UNIT_MEASURE" in group.columns:
            if "UNIT_MULT" in group.columns:
                pairs = (
                    group[["UNIT_MULT", "UNIT_MEASURE"]]
                    .dropna(subset=["UNIT_MEASURE"])
                    .drop_duplicates()
                )
                composites = []
                for _, pair in pairs.iterrows():
                    um = lookup_dict.get("UNIT_MEASURE", {}).get(pair["UNIT_MEASURE"], pair["UNIT_MEASURE"])
                    mult = pair["UNIT_MULT"]
                    if pd.notna(mult) and str(mult).strip() and str(mult) != "0":
                        mult_label = lookup_dict.get("UNIT_MULT", {}).get(str(mult), str(mult))
                        composites.append(f"{um} ({mult_label})")
                    else:
                        composites.append(um)
                row["UNIT_MEASURE"] = ", ".join(composites)
            else:
                units = group["UNIT_MEASURE"].dropna().unique()
                row["UNIT_MEASURE"] = ", ".join([
                    lookup_dict.get("UNIT_MEASURE", {}).get(u, u) for u in units
                ])
        else:
            row["UNIT_MEASURE"] = "N/A"

        # FREQ aggregation
        if "FREQ" in group.columns:
            freqs = group["FREQ"].dropna().unique()
            row["FREQ"] = ", ".join(freqs)
        else:
            row["FREQ"] = "N/A"

        # OBS_CONF aggregation
        if "OBS_CONF" in group.columns:
            conf = group["OBS_CONF"].dropna().unique()
            row["OBS_CONF"] = ", ".join(conf)
        else:
            row["OBS_CONF"] = "N/A"

        # TIME_PERIODS min/max
        if "TIME_PERIOD" in group.columns:
            years = group["TIME_PERIOD"].astype(str).unique()
            row["TIME_PERIODS"] = [{"start": years.min(), "end": years.max()}]

        # REF_AREA split into REF_COUNTRY/GEOGRAPHIC_UNITS
        if "REF_AREA" in df.columns:
            ref_codes = group["REF_AREA"].unique()
            row["REF_COUNTRY"] = [{"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                                 for c in ref_codes if c in country_codes]
            row["GEOGRAPHIC_UNITS"] = [{"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                           for c in ref_codes if c not in country_codes]
        row["DIMENSIONS"] = dimensions_dict.get(ind_code, [])
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)

    # Translate code to label dynamically
    id_column = "DATABASE_ID" if "DATABASE_ID" in summary_df.columns else "DATASET_ID"
    summary_df[f"{id_column.replace('_ID', '_NAME')}"] = (
        summary_df[id_column]
        .map(lookup_dict.get(id_column, {}))
        .fillna(summary_df[id_column])
    )
    summary_df["INDICATOR_NAME"] = summary_df["INDICATOR"].map(lookup_dict.get("INDICATOR", {})).fillna(summary_df["INDICATOR"])

    # Translate FREQ
    if "FREQ" in summary_df.columns:
        summary_df["FREQ"] = summary_df["FREQ"].apply(
            lambda x: ", ".join([lookup_dict.get("FREQ", {}).get(f, f) for f in x.split(", ")])
            if x != "N/A" else "N/A"
        )

    # Translate OBS_CONF
    if "OBS_CONF" in summary_df.columns:
        summary_df["OBS_CONF"] = summary_df["OBS_CONF"]

    return summary_df

def build_indicator_metadata_summary_spark(
        sdf, 
        schema, 
        env, 
        lookup_dict, 
        schema_summary, 
        country_codes,
        grouping_codes=None
    ):
    """
    Spark-native equivalent of build_indicator_metadata_summary + get_dimensions_with_lookup_dict.

    Computes all aggregates (collect_set, min, max) in Spark and collects only the small
    per-indicator summary to the driver — no full-table toPandas().

    Args:
        sdf: Spark DataFrame (gold Delta table or per-indicator CSVs via spark.read.csv).
        schema, env, lookup_dict, schema_summary, country_codes: same as the Pandas version.

    Returns:
        pd.DataFrame: Same structure as build_indicator_metadata_summary.
    """

    id_col = "DATABASE_ID" if "DATABASE_ID" in sdf.columns else "DATASET_ID"

    # Join country and grouping codes to identify later whether the indicator is subnational or not
    country_codes = set(country_codes)
    grouping_codes = set(grouping_codes) if grouping_codes is not None else set()
    all_ref_codes = country_codes.union(grouping_codes)

    # Mirror: df_valid = df[df["OBS_VALUE"].notna()]
    sdf_valid = sdf.filter(F.col("OBS_VALUE").isNotNull())

    agg_exprs = []

    if "TIME_PERIOD" in sdf.columns:
        agg_exprs += [
            F.min("TIME_PERIOD").alias("_time_min"),
            F.max("TIME_PERIOD").alias("_time_max"),
        ]

    # UNIT_MEASURE: struct pairs (for measurement_unit field) + plain set (for dimension check)
    if "UNIT_MULT" in sdf.columns and "UNIT_MEASURE" in sdf.columns:
        agg_exprs.append(
            F.collect_set(F.struct("UNIT_MULT", "UNIT_MEASURE")).alias("_unit_pairs")
        )
    if "UNIT_MEASURE" in sdf.columns:
        agg_exprs.append(F.collect_set("UNIT_MEASURE").alias("_set_UNIT_MEASURE"))

    for _col in ["FREQ", "OBS_CONF", "REF_AREA", "SEX", "URBANISATION", "AGE",
                 "COMP_BREAKDOWN_1", "COMP_BREAKDOWN_2", "COMP_BREAKDOWN_3"]:
        if _col in sdf.columns:
            agg_exprs.append(F.collect_set(_col).alias(f"_set_{_col}"))

    agg_rows = sdf_valid.groupBy(id_col, "INDICATOR").agg(*agg_exprs).collect()

    # Dimension list from schema (mirrors get_dimensions_with_lookup_dict)
    dim_list = schema_summary.loc[schema_summary["role"] == "DIMENSION", "component_id"].values

    summary_rows = []
    for r in agg_rows:
        rd = r.asDict(recursive=True)
        row = {id_col: rd[id_col], "INDICATOR": rd["INDICATOR"]}

        # --- UNIT_MEASURE field ---
        unit_pairs = rd.get("_unit_pairs")
        if unit_pairs is not None:
            valid_pairs = [p for p in unit_pairs if p.get("UNIT_MEASURE") is not None]
            composites = []
            for p in valid_pairs:
                um_label = lookup_dict.get("UNIT_MEASURE", {}).get(p["UNIT_MEASURE"], p["UNIT_MEASURE"])
                mult = p.get("UNIT_MULT")
                if mult and str(mult).strip() and str(mult) != "0":
                    mult_label = lookup_dict.get("UNIT_MULT", {}).get(str(mult), str(mult))
                    composites.append(f"{um_label} ({mult_label})")
                else:
                    composites.append(um_label)
            row["UNIT_MEASURE"] = ", ".join(composites) if composites else "N/A"
        else:
            units = [u for u in (rd.get("_set_UNIT_MEASURE") or []) if u is not None]
            row["UNIT_MEASURE"] = ", ".join([
                lookup_dict.get("UNIT_MEASURE", {}).get(u, u) for u in units
            ]) if units else "N/A"

        # --- FREQ ---
        freqs = [f for f in (rd.get("_set_FREQ") or []) if f is not None]
        row["FREQ"] = ", ".join(freqs) if freqs else "N/A"

        # --- OBS_CONF ---
        confs = [c for c in (rd.get("_set_OBS_CONF") or []) if c is not None]
        row["OBS_CONF"] = ", ".join(confs) if confs else "N/A"

        # --- TIME_PERIODS ---
        t_min, t_max = rd.get("_time_min"), rd.get("_time_max")
        row["TIME_PERIODS"] = [{"start": str(t_min), "end": str(t_max)}] if t_min else []

        # --- REF_AREA → REF_COUNTRY / GEOGRAPHIC_UNITS ---
        ref_codes = [c for c in (rd.get("_set_REF_AREA") or []) if c is not None]
        ref_codes = set(ref_codes)
        # Check if there are more codes in ref_codes that in all_ref_codes
        # If there are more codes, then it is subnational data
        # If there are no more codes, then it is national data
        extra_codes = ref_codes - all_ref_codes
        is_national = len(extra_codes) == 0

        if is_national:  # National data
            print(f"{rd['INDICATOR']} indicator has national data only...")
            row["REF_COUNTRY"] = [
                {"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                for c in ref_codes if c in country_codes
            ]
            row["GEOGRAPHIC_UNITS"] = [
                {"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                for c in ref_codes if c not in country_codes
            ]
        else:  # Subnational data
            print(f"{rd['INDICATOR']} indicator has subnational data...")
            row["REF_COUNTRY"] = [
                {"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                for c in ref_codes if c in country_codes
            ]
            row["GEOGRAPHIC_UNITS"] = [
                {"code": c, "name": lookup_dict.get("REF_AREA", {}).get(c, c)}
                for c in ref_codes if c in grouping_codes
            ]

        # --- DIMENSIONS (mirrors get_dimensions_with_lookup_dict) ---
        values = set()
        for dim in dim_list:
            if dim in ["INDICATOR", "OBS_VALUE", "FREQ", "UNIT_MEASURE"]:
                continue
            if dim == "REF_AREA":
                values.add(("Geographic area", "Country/economy, Region"))
                continue
            if dim == "SEX":
                if len(rd.get("_set_SEX") or []) > 1:
                    values.add(("Sex", "Total, Male, Female"))
                continue
            if dim == "URBANISATION":
                if len(rd.get("_set_URBANISATION") or []) > 1:
                    values.add(("Residential area", "Total, Urban, Rural"))
                continue
            if dim == "AGE":
                if len(rd.get("_set_AGE") or []) > 1:
                    values.add(("Age", ""))
                continue
            # For all other dimensions: check COMP_BREAKDOWN columns, else fall back to schema name
            cb_keys = [f"_set_{c}" for c in ["COMP_BREAKDOWN_1", "COMP_BREAKDOWN_2", "COMP_BREAKDOWN_3"]
                       if f"_set_{c}" in rd]
            if cb_keys:
                for cb_key in cb_keys:
                    col_name = cb_key.removeprefix("_set_")
                    for code in (rd[cb_key] or []):
                        if code in (None, "_T", "_Z"):
                            continue
                        mapped = lookup_dict.get(col_name, {}).get(code, code)
                        dim_label = mapped.split(":")[0].strip() if ":" in mapped else mapped
                        values.add((dim_label, ""))
            else:
                comp_name = schema_summary.loc[
                    schema_summary["component_id"] == dim, "component_name"
                ].values
                if len(comp_name) > 0:
                    values.add((comp_name[0], ""))

        # UNIT_MEASURE becomes a dimension when multiple units are present
        um_set = [u for u in (rd.get("_set_UNIT_MEASURE") or []) if u is not None]
        if len(um_set) > 1:
            translated = sorted([lookup_dict.get("UNIT_MEASURE", {}).get(u, u) for u in um_set])
            values.add(("Unit of measure", ", ".join(translated)))

        row["DIMENSIONS"] = [
            {"label": v[0]} if v[1] == "" else {"label": v[0], "description": v[1]}
            for v in values
        ]
        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    if summary_df.empty:
        return summary_df

    # Translate id/indicator codes to labels
    id_col_actual = "DATABASE_ID" if "DATABASE_ID" in summary_df.columns else "DATASET_ID"
    name_col = id_col_actual.replace("_ID", "_NAME")
    summary_df[name_col] = (
        summary_df[id_col_actual].map(lookup_dict.get(id_col_actual, {})).fillna(summary_df[id_col_actual])
    )
    summary_df["INDICATOR_NAME"] = (
        summary_df["INDICATOR"].map(lookup_dict.get("INDICATOR", {})).fillna(summary_df["INDICATOR"])
    )
    if "FREQ" in summary_df.columns:
        summary_df["FREQ"] = summary_df["FREQ"].apply(
            lambda x: ", ".join([lookup_dict.get("FREQ", {}).get(f, f) for f in x.split(", ")])
            if x != "N/A" else "N/A"
        )

    return summary_df


def build_database_metadata_summary(indicator_summary):
    """
    Build database-level summary from indicator-level summary DataFrame.
    """
    # --- Detect ID column dynamically ---
    id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in indicator_summary.columns), None)
    if id_column is None:
        raise ValueError("Neither 'DATABASE_ID' nor 'DATASET_ID' found in DataFrame columns.")

    # --- Detect name column dynamically ---
    name_column = next((col for col in ["DATABASE_NAME", "DATASET_NAME"] if col in indicator_summary.columns), None)

    db_rows = []

    for db_id, group in indicator_summary.groupby(id_column, dropna=False):
        # --- TIME_PERIODS -> min start, max end ---
        all_periods = [
            p
            for sublist in group.get("TIME_PERIODS", [])
            if isinstance(sublist, list)
            for p in sublist
            if isinstance(p, dict) and "start" in p and "end" in p
        ]
        if all_periods:
            start = min(p["start"] for p in all_periods)
            end = max(p["end"] for p in all_periods)
            time_periods = [{"start": start, "end": end}]
        else:
            time_periods = []
        
        # REF_COUNTRY -> union
        all_countries = []
        for sublist in group["REF_COUNTRY"]:
            all_countries.extend(sublist)
        # deduplicate by code
        ref_country = {c["code"]: c["name"] for c in all_countries}
        ref_country = [{"code": k, "name": v} for k, v in ref_country.items()]
        
        # GEOGRAPHIC_UNITS -> union
        all_groups = []
        for sublist in group["GEOGRAPHIC_UNITS"]:
            all_groups.extend(sublist)
        geo_units = {g["code"]: g["name"] for g in all_groups}
        geo_units = [{"code": k, "name": v} for k, v in geo_units.items()]
        
        # DATABASE_NAME -> take the first
        db_name = (
            group[name_column].dropna().iloc[0]
            if name_column and not group[name_column].dropna().empty
            else None
        )

        db_rows.append({
            id_column: db_id,
            "TIME_PERIODS": time_periods,
            "REF_COUNTRY": ref_country,
            "GEOGRAPHIC_UNITS": geo_units,
            name_column: db_name if name_column else None
        })
    
    return pd.DataFrame(db_rows)






