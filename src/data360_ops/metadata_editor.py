import pandas as pd
from pymetadataeditor import MetadataEditor 
from .utils import extract_value_from_key
import requests
import json
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from databricks.sdk.runtime import dbutils
import time

def get_projects_from_collection(
		api_key: str,
		api_url: str='https://metadataeditor.worldbank.org/index.php/api',
		collections: int|list=[22,820]
	) -> pd.DataFrame:
	"""Function to get projects from a list of collections and return a combined dataframe with additional columns
	
	Args:
		api_key (str): API key for authentication.
		api_url (str): The base URL of the API. 
		collections (int|list): A single collection number or a list of collection numbers to extract projects from. Defaults to [22, 820], where 22 is Data360 public collection and 820 is Data360 Official Use collection.
	returns:
		pd.DataFrame: A combined dataframe with projects from all specified collections, including additional columns for confidentiality and dataset_id.
	"""
	# Transform collections to list if it's a single integer
	if isinstance(collections, int):
		collections = [collections]

	# Initialize MetadataEditor instance
	me = MetadataEditor(api_url=api_url, api_key=api_key, verify_ssl=False)

	# Initialize an empty dataframe to store combined projects
	me_projects_df = pd.DataFrame()

	# Extract all projects from both collections and combine into a single dataframe
	for col in collections:
		print(f"Extracting metadata projects in collection: {col}")
		temp_df = me.list_projects_in_collection(collection=col, limit='All')
		# Extract information from columns with dictionaries
		temp_df['dataset_id'] = temp_df['attributes'].apply(
			lambda x: extract_value_from_key(x, 'database_id'))
		temp_df['collection_id'] = col
		temp_df['collection_title'] = temp_df['collections'].\
			apply(lambda x: next(
				(extract_value_from_key(item, 'title') for item in x 
	 				if item['id'] == str(col)), None))
		# Transform created and changed columns to datetime with timezone into account
		temp_df['created_utc'] = pd.to_datetime(temp_df['created'], utc=True)
		temp_df['changed_utc'] = pd.to_datetime(temp_df['changed'], utc=True)
		# Ignore hour from created and changed columns
		temp_df['created_utc_date'] = temp_df['created_utc'].dt.normalize() #type: ignore
		temp_df['changed_utc_date'] = temp_df['changed_utc'].dt.normalize() #type: ignore
		# Concatenate to main dataframe
		me_projects_df = pd.concat([me_projects_df, temp_df], ignore_index=False)
	
	# Reset index after concatenation
	me_projects_df.reset_index(drop=False, inplace=True)

	return me_projects_df


def filter_projects_by_changed_date(
		projects_df: pd.DataFrame,
		start_date: str|None=None,
		end_date: str|None=None) -> pd.DataFrame:
	"""Filter projects dataframe based on a date range for the changed_utc_date column.
	If start_date and end_date are empty, this function will return projects modified in the last 48 hours.

	The reason for using last 48 hours instead of last 24 hours is to account for any timezone differences and ensure we capture all projects modified "today" in any timezone.

	Args:
		projects_df (pd.DataFrame): DataFrame containing projects with a 'changed_utc_date' column.
		start_date (str): Start date in 'YYYY-MM-DD' format.
		end_date (str): End date in 'YYYY-MM-DD' format.

	Returns:
		pd.DataFrame: Filtered DataFrame containing projects where 'changed_utc_date' is between the specified start and end dates.
	"""
	# Set start and end dates as timestamps with timezone
	today = pd.Timestamp.today()
	if start_date is None:
		# Set start_date to 48 hours ago to account for timezone differences and ensure we capture all projects modified "today" in any timezone
		starting_date = pd.Timestamp((today - pd.Timedelta(days=1)).normalize(), tz='UTC')
	else:
		starting_date = pd.Timestamp(start_date, tz='UTC')

	if end_date is None:
		ending_date = pd.Timestamp((today + pd.Timedelta(days=1)).normalize(), tz='UTC')
	else:
		ending_date = pd.Timestamp(end_date, tz='UTC')

	filtered_projects_range = projects_df[
		(projects_df['changed_utc_date'] >= starting_date) & 
		(projects_df['changed_utc_date'] <= ending_date)].copy()
	
	return filtered_projects_range


###### Functions from publishing.py script developed by Echo
def get_exist_meta_id(
		key, type, collection_num = 22,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to extract the existing metadata id from the metadata editor
	:param meta_url: metadata editor url
	:param key: api key
	:return: dictionary of existing metadata id
	"""
	limit = 1000  # Max limit per page
	request_url = (
		f"{meta_url}/api/editor?collection={collection_num}&type={type}&limit={limit}&offset=0"
	)
	headers = {"x-api-key": key}
	response = requests.request("GET", request_url, headers=headers)
	result = response.json()

	if response.status_code != 200:
		exist_id = response.text
	else:
		total_cases = result["total"]
		exist_id = dict()

		for i in range(0, total_cases, limit):
			paginated_url = f"{meta_url}/api/editor?collection={collection_num}&type={type}&limit={limit}&offset={i}"
			paginated_response = requests.get(paginated_url, headers=headers)

			paginated_result = paginated_response.json()
			projects = paginated_result["projects"]

			for item in projects:
				exist_id[item["study_idno"]] = item["id"]

	if exist_id == {}:  # stop the pipeline if no metadata projects are found
		# log.error("No existing Data360 metadata projects found! Check your Metadata Editor account role.")
		print("No existing Data360 metadata projects found! Check your Metadata Editor account role.")
		raise Exception("No existing Data360 metadata projects found!")
	else:
		# log.info("Existing Data360 metadata projects found (type=%s, collection=%s)", type, collection_num)
		print(f"Existing Data360 metadata projects found (type={type}, collection={collection_num})")
		return exist_id
	
def get_exist_meta_id_across_collections(
		key, project_type, collection_nums, 
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Query metadata projects across one or more collections and return a merged idno→id dict.
	Tolerates empty collections (returns {} if nothing found; caller is responsible for missing-project checks).
	Raises RuntimeError if the API returns a non-200 response.
	"""
	merged = {}
	headers = {"x-api-key": key}
	limit = 1000
	for col_num in collection_nums:
		url = f"{meta_url}/api/editor?collection={col_num}&type={project_type}&limit={limit}&offset=0"
		resp = requests.get(url, headers=headers)
		if resp.status_code != 200:
			raise RuntimeError(f"Metadata API error querying collection {col_num}: {resp.text}")
		result = resp.json()
		total = result.get("total", 0)
		for i in range(0, total, limit):
			page_url = f"{meta_url}/api/editor?collection={col_num}&type={project_type}&limit={limit}&offset={i}"
			page_resp = requests.get(page_url, headers=headers)
			for item in page_resp.json().get("projects", []):
				merged[item["study_idno"]] = item["id"]
		# log.info("Collection %s queried: %d total projects (type=%s)", col_num, total, project_type)
		print(f"Collection {col_num} queried: {total} total projects (type={project_type})")
	return merged

def get_meta_by_dataset_db(
		dataset_id, api_key, type, collection_num,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Extract Data360 metadata projects belonging to a dataset.

	:param meta_url: Base URL of metadata API
	:param dataset_id: Dataset identifier
	:param api_key: API key
	:param type: "timeseries" or "timeseries-db"
	:return: DataFrame of metadata projects
	"""
	limit = 1000  # Max limit per page
	headers = {"x-api-key": api_key}

	request_url = f"{meta_url}/api/editor?collection={collection_num}&type={type}&limit={limit}&offset=0"
	response = requests.get(request_url, headers=headers)
	result = response.json()

	if response.status_code != 200:
		raise RuntimeError(f"Metadata request failed: {response.text}")

	total_cases = result.get("total", 0)
	exist_id = {}

	for i in range(0, total_cases, limit):
		paginated_url = f"{meta_url}/api/editor?collection={collection_num}&type={type}&limit={limit}&offset={i}"
		paginated_response = requests.get(paginated_url, headers=headers)
		paginated_result = paginated_response.json()
		projects = paginated_result.get("projects", [])

		if type == "timeseries":
			for item in projects:
				if not isinstance(item, dict):
					continue

				attrs = item.get("attributes")
				if not isinstance(attrs, dict):
					continue    

				if attrs.get("database_id") == dataset_id.upper():
					exist_id[item["study_idno"]] = item["id"]
					# log.info("Found existing metadata project for indicator %s", item["id"])
					print(f"Found existing metadata project for indicator {item['id']} in collection {collection_num}")

		elif type == "timeseries-db":
			for item in projects:
				if not isinstance(item, dict):
					continue

				if item.get("study_idno") == dataset_id:
					exist_id[item["study_idno"]] = item["id"]
					# log.info("Found existing metadata project for dataset %s", dataset_id)
					print(f"Found existing metadata project for dataset {dataset_id} in collection {collection_num}")

	if not exist_id:
		raise Exception("No existing Data360 metadata projects found! Check your Metadata Editor account role.")
	else:
		# log.info("Existing Data360 metadata projects found (%d total)", len(exist_id))
		print(f"Existing Data360 metadata projects found ({len(exist_id)} total)")
		meta_id = (
			pd.DataFrame.from_dict(exist_id, orient="index", columns=["idno"])
			.reset_index()
		)
		return meta_id

def get_meta_by_dataset_db_across_collections(
		dataset_id, api_key, type, collection_nums, 
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Like get_meta_by_dataset_db, but merges results across multiple collections and
	tolerates a collection where this dataset has nothing (get_meta_by_dataset_db raises
	per-collection when nothing is found there — expected when a project is filed in
	exactly one of draft/prod, not both). Raises only if the dataset is found in none of
	the given collections.
	"""
	frames = []
	print("")
	for collection_num in collection_nums:
		try:
			frames.append(get_meta_by_dataset_db(
				meta_url=meta_url, dataset_id=dataset_id, api_key=api_key, 
				type=type, collection_num=collection_num))
		except Exception as e:
			# log.info("No %s projects for %s in collection %s (%s)", type, dataset_id, collection_num, e)
			print(f"No {type} projects for {dataset_id} in collection {collection_num}: Error ({e})")
	if not frames:
		raise RuntimeError(
			f"No {type} projects found for dataset '{dataset_id}' in any of collections {collection_nums}."
		)
	return pd.concat(frames, ignore_index=True).drop_duplicates(subset="idno").reset_index(drop=True)

def update_project(
		md, key, idno, project_type = "timeseries", partial_update = True,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to update a timeseries project in the metadata editor
	:param md: metadata in json format
	:param key: api key
	:param idno: idno of the project
	:param partial_update: boolean value to update the metadata
	:return: response of the update
	"""
	metadata_json = md
	request_url = f"{meta_url}/api/editor/update/{project_type}/{idno}?id_format=idno&partial_update={partial_update}"
	headers = {"x-api-key": key, "Content-Type": "application/json"}
	response = requests.request(
		"POST", request_url, headers=headers, data=metadata_json
	)
	if response.status_code != 200:
		# log.warning("update_project %s returned %s: %s", idno, response.status_code, response.text)
		print(f"update_project {idno} returned {response.status_code}: {response.text}")
	r = response.text
	return r

def create_project(
		md, key, project_type = "timeseries",
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to create a timeseries project in the metadata editor
	:param md: metadata in json format
	:param key: api key
	:return: idno of the project
	"""
	request_url = f"{meta_url}/api/editor/create/{project_type}"
	metadata_json = md
	headers = {"x-api-key": key}
	response = requests.request(
		"POST", request_url, headers=headers, data=metadata_json
	)
	if response.status_code != 200:
		return response.text
	idno = json.loads(response.text)["id"]
	
	return {"idno": idno}

def check_geo_unit(
		idno, key, project_type, 
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Check if key 'geographic_units' exists in the JSON metadata.

	:param idno: Numeric idno generated once the project is created
	:param key: API key
	:return: True if 'geographic_units' exists, False otherwise
	"""
	headers = {"x-api-key": key}
	request_url = f"{meta_url}/api/editor/json/{idno}"

	try:
		response = requests.get(request_url, headers=headers)
		response.raise_for_status()
		json_data = response.json()
		if project_type == "timeseries":
			return (
				"series_description" in json_data
				and "geographic_units" in json_data["series_description"]
			)
		elif project_type == "timeseries-db":
			return (
				"database_description" in json_data
				and "geographic_units" in json_data["database_description"]
			)
		else:
			# log.warning("Project %s (type=%s) has no geographic_units field", idno, project_type)
			print(f"Project {idno} (type={project_type}) has no geographic_units field")
	except requests.exceptions.RequestException as e:
		# log.error("Error fetching data for idno %s: %s", idno, e)
		print(f"Error fetching data for idno {idno}: {e}")
	except ValueError:
		# log.error("Invalid JSON response for idno %s", idno)
		print(f"Invalid JSON response for idno {idno}")

	return False

def update_patch(
		md, key, idno, project_type = "timeseries",
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to update a project through patch in the metadata editor
	:param md: metadata in json format
	:param key: api key
	:param idno: idno of the project
	:param partial_update: boolean value to update the metadata
	:return: response of the update
	"""
	metadata_json = md
	request_url = f"{meta_url}/api/editor/patch/{project_type}/{idno}?id_format=idno"
	headers = {"x-api-key": key, "Content-Type": "application/json"}
	response = requests.request(
		"POST", request_url, headers=headers, data=metadata_json
	)
	if response.status_code != 200:
		# log.warning("update_patch %s returned %s: %s", idno, response.status_code, response.text)
		print(f"update_patch {idno} returned {response.status_code}: {response.text}")
	r = response.text
	return r

def add_data360_admin_metadata(
		df, key,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to add the project to data360 collection
	:param df: dataFrame with column 'numid'
	:param key: api key
	:return: response of the add project
	"""
	responses = []
	projects = df["numid"].astype(str).tolist()
	for _,row in df.iterrows():
		admin_meta = {
				"project_id": row["numid"],
				"template_uid": "data360",
					"metadata": {
						"visualization": {
							"remove_chart": [
								{"chart_types": "stackedBar"},
								{"chart_types": "pie"},
								{"chart_types": "boxplot"}
							]
						}
					}
				}
		md = json.dumps(admin_meta)
		request_url = f"{meta_url}/api/admin-metadata/data/"
		headers = {"x-api-key": key, "Content-Type": "application/json"}
		response = requests.request("POST", request_url, headers=headers, data=md)
		if response.status_code != 200:
			# log.warning("add_data360_admin_metadata failed for %s: %s", row['numid'], response.text)
			print(f"add_data360_admin_metadata failed for {row['numid']}: {response.text}")
		responses.append(f"{row['numid']}: {response.text}")

	return responses

def add_project_to_collection(
		df, key, collection_num,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Function uses to add the project to a collection
	:param df: dataFrame with column 'numid'
	:param key: api key
	:return: response of the add project
	"""
	projects = df["numid"].astype(str).tolist()
	add_collection = {"collections": collection_num, "id_format": "idno", "projects": projects}
	json_add_collection = json.dumps(add_collection)

	request_url = f"{meta_url}/api/collections/add_projects"
	headers = {"x-api-key": key, "Content-Type": "application/json"}
	response = requests.request(
		"POST", request_url, headers=headers, data=json_add_collection
	)
	if response.status_code != 200:
		# log.warning("add_project_to_collection returned %s: %s", response.status_code, response.text)
		print(f"add_project_to_collection returned {response.status_code}: {response.text}")
	r = response.text

	return r

def manage_collection_projects(
		projects, key, action, collection_id, 
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	"""
	Add or remove individual projects from a Metadata Editor collection.

	:param projects: List of numeric project IDs, or a DataFrame with a 'numid' column
	:param key: API key
	:param action: "add" or "remove"
	:param collection_id: Target collection ID (integer)
	:return: Dict with status_code, response, and http_response

	Note: `id_format` is deliberately "id", not "idno" — `projects` are numeric database
	IDs (numid), not idno strings. Sending "idno" here matches nothing on the remove_projects
	endpoint (it silently reports success on 0 matched rows), even though add_projects happens
	to tolerate the mismatch. Confirmed via manual API testing against a live collection.
	"""
	if isinstance(projects, pd.DataFrame):
		project_ids = projects["numid"].dropna().astype(int).tolist()
	else:
		project_ids = [int(p) for p in projects]

	if action not in ("add", "remove"):
		raise ValueError(f"action must be 'add' or 'remove', got {action!r}")

	endpoint = "add_projects" if action == "add" else "remove_projects"
	request_url = f"{meta_url}/api/collections/{endpoint}"
	payload = json.dumps({
		"collections": [int(collection_id)],
		"id_format": "id",
		"projects": project_ids,
	})
	headers = {"x-api-key": key, "Content-Type": "application/json"}
	response = requests.post(request_url, headers=headers, data=payload)

	if response.status_code != 200:
		# log.warning("manage_collection_projects %s collection %s returned %s: %s",
		#             action, collection_id, response.status_code, response.text)
		print(f"manage_collection_projects {action} collection {collection_id} returned {response.status_code}: {response.text}")
	else:
		# log.info("manage_collection_projects: %s %d project(s) %s collection %s",
		#          action, len(project_ids), "to" if action == "add" else "from", collection_id)
		print(f"manage_collection_projects: {action} {len(project_ids)} project(s) {'to' if action == 'add' else 'from'} collection {collection_id}")

	return {
		"status_code": response.status_code,
		"response": response.json() if response.text else {},
		"http_response": response,
	}

def clean_admin_metadata(raw_json: dict) -> dict:
	"""
	Transform admin metadata API response into simplified structure.

	Input structure:
		{status, data:[{template_uid, metadata, ...}]}

	Output structure:
		{admin_metadata:{template_uid: metadata}}
	"""
	return {
		"admin_metadata": {
			item["template_uid"]: item.get("metadata", {})
			for item in raw_json.get("data", [])
			if item.get("template_uid")
		}
	}

def fetch_and_save(session, url, path, is_pdf=False, clean_admin=False):
	r = session.get(url, stream=is_pdf)
	r.raise_for_status()

	if is_pdf:
		with open(path, "wb") as f:
			for chunk in r.iter_content(8192):
				f.write(chunk)
	else:
		data = r.json()
		if clean_admin:
			data = clean_admin_metadata(data)
		with open(path, "w") as f:
			json.dump(data, f)

def export_object(
		session, obj_id, obj_name, folders, admin=False,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	results = {}

	try:
		if admin:
			url = f"{meta_url}/api/admin-metadata/data/{obj_id}"
			path = f"{folders['json']}/{obj_name}.json"
			fetch_and_save(session, url, path, clean_admin=True)
			results["json"] = path

		else:
			json_url = f"{meta_url}/api/editor/json/{obj_id}?exclude_private_fields=1"
			pdf_gen = f"{meta_url}/api/editor/generate_pdf/{obj_id}?exclude_private_fields=1"
			pdf_url = f"{meta_url}/api/editor/pdf/{obj_id}"

			json_path = f"{folders['json']}/{obj_name}.json"
			pdf_path = f"{folders['pdf']}/{obj_name}.pdf"

			fetch_and_save(session, json_url, json_path)
			session.get(pdf_gen).raise_for_status()
			fetch_and_save(session, pdf_url, pdf_path, is_pdf=True)

			results = {"json": json_path, "pdf": pdf_path}

	except Exception as e:
		results["error"] = str(e)

	return obj_name, results

def export_metadata_all(
    dataset_id,
    api_key,
    catalog_env,
    obs_conf_path,
    collection_num,
    indicator_list=None,
    admin=False,
    workers=8,
    df_ind=None,
    df_db=None,
    meta_url: str='https://metadataeditor.worldbank.org/index.php'
):
    
    root = f"/Volumes/{catalog_env}_data360/volumes/data360-dropzone/{obs_conf_path}/datasets/{dataset_id}/metadata"

    folders = {
        "ind_json": f"{root}/admin_metadata" if admin else root,
        "ind_pdf": f"{root}/download",
        "db_json": f"{root}/dataset/admin_metadata" if admin else f"{root}/dataset",
        "db_pdf": f"{root}/dataset/download"
    }

    # For admin pass, only manage the json output folders — pdf folders belong to the
    # main-metadata pass and must not be wiped after they've been written.
    folders_to_manage = (
        {k: v for k, v in folders.items() if "pdf" not in k}
        if admin else folders
    )

    for f in folders_to_manage.values():
        if indicator_list is None:
            # Full export -> recreate folders
            dbutils.fs.rm(f, recurse=True)
            dbutils.fs.mkdirs(f)
        else:
            # Partial update -> keep existing files
            try:
                dbutils.fs.ls(f)
            except:
                dbutils.fs.mkdirs(f)

    session = requests.Session()
    session.headers.update({"x-api-key": api_key})

    if df_ind is None or df_db is None:
        # log.info("Fetching metadata objects for %s...", dataset_id)
        print(f"Fetching metadata objects for {dataset_id}...")
        df_ind = get_meta_by_dataset_db(meta_url=meta_url, dataset_id=dataset_id, api_key=api_key, type="timeseries", collection_num=collection_num)
        df_db = get_meta_by_dataset_db(meta_url=meta_url, dataset_id=dataset_id, api_key=api_key, type="timeseries-db", collection_num=collection_num)

    if indicator_list:
        df_ind = df_ind[df_ind["index"].isin(indicator_list)]

    tasks = []

    with ThreadPoolExecutor(max_workers=workers) as executor:

        for df, j, p in [
            (df_db, folders["db_json"], folders["db_pdf"]),
            (df_ind, folders["ind_json"], folders["ind_pdf"])
        ]:

            for row in df.itertuples():
                tasks.append(
                    executor.submit(
                        export_object,
                        session=session,
                        obj_id=row.idno,
                        obj_name=row.index,
                        folders={"json": j, "pdf": p},
                        admin=admin,
                        meta_url=meta_url,
                    )
                )

        results = {}
        for f in as_completed(tasks):
            name, res = f.result()
            results[name] = res

    # log.info("Export completed for dataset %s (admin=%s)", dataset_id, admin)
    print(f"Export completed for dataset {dataset_id} (admin={admin})")
    return results

def export_all_metadata(
    dataset_id,
    api_key,
    catalog_env,
    obs_conf_path,
    collection_num,
    indicator_list=None,
    df_ind=None,
    df_db=None,
    meta_url: str='https://metadataeditor.worldbank.org/index.php'
):
    """Export both standard metadata and admin metadata efficiently.

    Pass df_ind/df_db (e.g. from get_meta_by_dataset_db_across_collections) to export an
    already-resolved set of projects instead of fetching from a single collection_num —
    used by the QA export path, which merges draft + prod rather than querying one
    collection.
    """

    if df_ind is None or df_db is None:
        # log.info("Fetching metadata objects for %s...", dataset_id)
        print(f"Fetching metadata objects for {dataset_id}...")
        df_ind = get_meta_by_dataset_db(meta_url=meta_url, dataset_id=dataset_id, api_key=api_key, type="timeseries", collection_num=collection_num)
        df_db  = get_meta_by_dataset_db(meta_url=meta_url, dataset_id=dataset_id, api_key=api_key, type="timeseries-db", collection_num=collection_num)

    results = {}

    results["metadata"] = export_metadata_all(
        meta_url=meta_url,
        dataset_id=dataset_id,
        api_key=api_key,
        catalog_env=catalog_env,
        obs_conf_path=obs_conf_path,
        collection_num=collection_num,
        indicator_list=indicator_list,
        admin=False,
        df_ind=df_ind,
        df_db=df_db
    )

    results["admin_metadata"] = export_metadata_all(
        meta_url=meta_url,
        dataset_id=dataset_id,
        api_key=api_key,
        catalog_env=catalog_env,
        obs_conf_path=obs_conf_path,
        collection_num=collection_num,
        indicator_list=indicator_list,
        admin=True,
        df_ind=df_ind,
        df_db=df_db
    )

    return results

def gen_metadata_information(indicator_name_short, indicator_id):
	"""
	# A function to generate standard metadata information for a given project
	:param indicator_name_short: short name of the indicator
	:param indicator_id: indicator id
	:param today: date of metadata creation
	:param vno: version number
	:param dm: date of version
	:return:
	"""
	metadata_information = dict()
	# metadata_information['partial_update'] = True
	metadata_information["title"] = f"Metadata for {indicator_name_short}"
	metadata_information["idno"] = f"META_{indicator_id}"

	metadata_information["producers"] = list()
	metadata_producer1 = dict()
	metadata_producer1["name"] = "Development Economics Data Group"
	metadata_producer1["abbr"] = "DECDG"
	metadata_producer1["affiliation"] = "World Bank"
	metadata_information["producers"].append(metadata_producer1)

	metadata_information["version_statement"] = {
		"version_date": date.today().isoformat(),
		"version_notes": "Metadata updated by automated Data360 publishing pipeline",
	}

	return metadata_information

def gen_series_description(stamp_version=True, **kwargs):
	"""
	A function to generate standard series_description for a given project
	:param vno: version number
	:param dm: date of version
	:param stamp_version: if True (default), stamp version_statement.version_date with
		today's date. Set False for routine pipeline updates so this curator-owned field
		isn't overwritten on every run — only on genuine (re)creation.
	:param kwargs: a dictionary of metadata information
	"""
	series_description = {}

	# Title statement
	series_description["name"] = kwargs.get("name", "")
	series_description["idno"] = kwargs.get("idno", "")
	series_description["database_id"] = kwargs.get("database_id", "")
	series_description["database_name"] = kwargs.get("database_name", "")
	series_description["languages"] = [{"name": "English", "code": "EN"}]

	# Description
	# series_description["definition_long"] = kwargs.get("definition_long", "")
	# series_description["definition_references"] = kwargs.get(
	#     "definition_references", ""
	# )
	series_description["measurement_unit"] = kwargs.get("measurement_unit", "")
	series_description["dimensions"] = kwargs.get("dimensions", "")
	series_description["periodicity"] = kwargs.get("periodicity", "")
	series_description["aggregation_method"] = kwargs.get("aggregation_method", "")

	# Geographic and time coverage
	series_description["time_periods"] = kwargs.get("time_periods", "")
	series_description["ref_country"] = kwargs.get("ref_country", "")
	series_description["geographic_units"] = kwargs.get("geographic_units", "")

	# Access and use
	# series_description["license"] = kwargs.get("license", "")
	series_description["confidentiality_status"] = kwargs.get("confidentiality_status", "")    

	# Version — curator-owned; only stamp on (re)creation, not on routine pipeline updates.
	if stamp_version:
		series_description["version_statement"] = {
			"version_date": date.today().isoformat(),
		}

	# Put DDH download link here if available
	series_description["links"] = kwargs.get("links", "")

	# Remove keys with empty values
	series_description = {k: v for k, v in series_description.items() if v}

	return series_description

def gen_database_description(stamp_version=True, **kwargs):
	"""
	A function to generate standard database_description for a given project
	:param vno: version number
	:param dm: date of version
	:param stamp_version: if True (default), stamp version[0].date with today's date.
		Set False for routine pipeline updates so this curator-owned field isn't
		overwritten on every run — only on genuine (re)creation.
	:param kwargs: a dictionary of metadata information
	"""
	database_description = {}

	# Title statement
	database_description["title_statement"] = {
		"idno": kwargs.get("idno", ""),
		"title": kwargs.get("title", "")}
	database_description["languages"] = [{"name": "English", "code": "EN"}]

	# Geographic and time coverage
	database_description["time_coverage"] = kwargs.get("time_periods", "")
	database_description["ref_country"] = kwargs.get("ref_country", "")
	database_description["geographic_units"] = kwargs.get("geographic_units", "")

	# Version — curator-owned; only stamp on (re)creation, not on routine pipeline updates.
	if stamp_version:
		database_description["version"] = [{
			"date": date.today().isoformat()
		}]

	# Remove keys with empty values
	database_description = {k: v for k, v in database_description.items() if v}

	return database_description

def gen_metadata_payloads(row, id_column, stamp_version=True):
	metadata_content = gen_metadata_information(row["INDICATOR_NAME"], row["INDICATOR"])
	indicator_content = gen_series_description(
		stamp_version=stamp_version,
		name=row["INDICATOR_NAME"],
		idno=row["INDICATOR"],
		database_id=row[id_column],
		database_name=row[id_column.replace("_ID", "_NAME")],
		measurement_unit=row["UNIT_MEASURE"],
		dimensions=row["DIMENSIONS"],
		periodicity=row["FREQ"],
		confidentiality_status=row['OBS_CONF'],
		time_periods=row["TIME_PERIODS"],
		ref_country=row["REF_COUNTRY"],
		geographic_units=row["GEOGRAPHIC_UNITS"],
	)
	meta_project = {
		"partial_update": True,
		"metadata_information": metadata_content,
		"series_description": indicator_content,
	}

	return json.dumps(meta_project)

def gen_metadata_payloads_database(row, id_column, name_column, stamp_version=True):
	metadata_content = gen_metadata_information(row[name_column], row[id_column])
	indicator_content = gen_database_description(
		stamp_version=stamp_version,
		title=row[name_column],
		idno=row[id_column],
		time_periods=row["TIME_PERIODS"],
		ref_country=row["REF_COUNTRY"],
		geographic_units=row["GEOGRAPHIC_UNITS"],
	)
	meta_project = {
		"partial_update": True,
		"metadata_information": metadata_content,
		"database_description": indicator_content,
	}

	return json.dumps(meta_project)

def gen_metadata_patch(row, geo_exist_boolean):
    """
    Generate a metadata patch update payload for fields with list values.

    :param row: Dictionary containing row data
    :param geo_exist_boolean: Boolean indicating if 'geographic_units' exists in the metadata
    :return: JSON string representing the patch update
    """
    patch_values = [
        {
            "value": row[col],
            "op": "replace",
            "path": f"/series_description/{col.lower()}",
        }
        for col in ["DIMENSIONS", "REF_COUNTRY"]
        if row.get(col)
    ]

    geo_value = row.get("GEOGRAPHIC_UNITS", [])

    if geo_exist_boolean:
        value = geo_value if geo_value else [{"name": "", "code": "", "type": ""}]
        op = "replace"
    elif geo_value:
        value = geo_value
        op = "add"
    else:
        value = None

    if value is not None:
        patch_values.append({
            "value": value,
            "op": op,
                "path": "/series_description/geographic_units",
            }
        )

    return json.dumps({"patches": patch_values, "validate": "true"})

def gen_metadata_patch_database(row, geo_exist_boolean, stamp_version=True):
    """
    Generate a metadata patch update payload for fields with list values.

    :param row: Dictionary containing row data
    :param geo_exist_boolean: Boolean indicating if 'geographic_units' exists in the metadata
    :param stamp_version: if True (default), prepend a new version/date entry. Set False for
        routine pipeline updates so this curator-owned field isn't overwritten on every run —
        only on genuine (re)creation.
    :return: JSON string representing the patch update
    """
    patch_values = [
        {
            "value": row["TIME_PERIODS"],
            "op": "replace",
            "path": "/database_description/time_coverage",
        },
        {
            "value": row["REF_COUNTRY"],
            "op": "replace",
            "path": "/database_description/ref_country",
        },
    ]

    if stamp_version:
        patch_values.append({
            "value": {"date": date.today().isoformat()},
            "op": "add",
            "path": "/database_description/version/0",
        })

    geo_value = row.get("GEOGRAPHIC_UNITS", [])

    if geo_exist_boolean:
        value = geo_value if geo_value else [{"name": "", "code": "", "type": ""}]
        op = "replace"
    elif geo_value:
        value = geo_value
        op = "add"
    else:
        value = None

    if value is not None:
        patch_values.append({
            "value": value,
            "op": op,
            "path": "/database_description/geographic_units"
        })

    return json.dumps({"patches": patch_values, "validate": False})

def create_edit_metadata_project_indicator(df, api_key, collection_num):
    """
    Function uses to create or update metadata for the dataset
    :param df: metadata df
    :param api_key: api key for metadata editor
    :param data_version_number: version number of the dataset
    :return: dataframe with metadata id
    """
    # Get existing data360 metadata project INDICATOR id and idno
    exist_id = get_exist_meta_id(api_key, "timeseries", collection_num)
    if not isinstance(exist_id, dict):
        raise RuntimeError("Metadata API is not responding")

    id_column = None
    for col in ["DATABASE_ID", "DATASET_ID"]:
        if col in df.columns:
            id_column = col
            break

    new_indices = []

    for index, row in df.iterrows():
        json_data = gen_metadata_payloads(row, id_column)
        # log.info("Metadata payloads created for %s", row["INDICATOR"])
        print(f"Metadata payloads created for {row['INDICATOR']}")
        # Check if INDICATOR_FINAL already exists in metadata
        # if it exists, save the idno and update the current metadata project
        if row["INDICATOR"] in exist_id.keys():
            df.loc[index, "numid"] = exist_id[row["INDICATOR"]]
            update_project(
                json_data, api_key, exist_id[row["INDICATOR"]], "timeseries", True
            )
            # log.info("Metadata project partial updated for %s", row["INDICATOR"])
            print(f"Metadata project partial updated for {row['INDICATOR']}")
            geo_exist_boolean = check_geo_unit(exist_id[row["INDICATOR"]], api_key, "timeseries")
            patch_json = gen_metadata_patch(row, geo_exist_boolean)
            update_patch(patch_json, api_key, exist_id[row["INDICATOR"]], "timeseries")
            # log.info("Metadata project patch updated for %s", row["INDICATOR"])
            print(f"Metadata project patch updated for {row['INDICATOR']}")

        # if it doesn't exist, create a new metadata project
        else:
            df.loc[index, "numid"] = create_project(json_data, api_key, "timeseries").get("idno")
            new_indices.append(index)

    if new_indices:
        add_data360_admin_metadata(df.loc[new_indices], api_key)

    add_project_to_collection(df, api_key, collection_num)

    return df

def create_edit_metadata_project_database(df, api_key, collection_num):
    """
    Function uses to create or update metadata for the dataset
    :param df: metadata df
    :param api_key: api key for metadata editor
    :param data_version_number: version number of the dataset
    :return: dataframe with metadata id
    """
    # Get existing data360 metadata project DATABASE_ID id and idno
    exist_id = get_exist_meta_id(api_key, "timeseries-db", collection_num)
    if not isinstance(exist_id, dict):
        raise RuntimeError("Metadata API is not responding")

    id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in df.columns), None)
    if id_column is None:
        raise ValueError("Neither 'DATABASE_ID' nor 'DATASET_ID' found in DataFrame columns.")

    name_column = next((col for col in ["DATABASE_NAME", "DATASET_NAME"] if col in df.columns), None)

    new_indices = []

    for index, row in df.iterrows():
        json_data = gen_metadata_payloads_database(row, id_column, name_column)
        # log.info("Metadata payloads created for %s", row[id_column])
        print(f"Metadata payloads created for {row[id_column]}")
        # Check if INDICATOR_FINAL already exists in metadata
        # if it exists, save the idno and update the current metadata project
        if row[id_column] in exist_id.keys():
            df.loc[index, "numid"] = exist_id[row[id_column]]
            update_project(
                json_data, api_key, exist_id[row[id_column]], 'timeseries-db', True
            )
            # log.info("Metadata project partial updated for %s", row[id_column])
            print(f"Metadata project partial updated for {row[id_column]}")

            geo_exist_boolean = check_geo_unit(exist_id[row[id_column]], api_key, "timeseries-db")
            patch_json = gen_metadata_patch_database(row, geo_exist_boolean)
            update_patch(patch_json, api_key, exist_id[row[id_column]], "timeseries-db")
            # log.info("Metadata project patch updated for %s", row[id_column])
            print(f"Metadata project patch updated for {row[id_column]}")

        # if it doesn't exist, create a new metadata project
        else:
            response = create_project(json_data, api_key, "timeseries-db")
            df.loc[index, "numid"] = response.get("idno")
            new_indices.append(index)
            # log.info("New database metadata project created for %s", row[id_column])
            print(f"New database metadata project created for {row[id_column]}")

    if new_indices:
        add_data360_admin_metadata(df.loc[new_indices], api_key)

    add_project_to_collection(df, api_key, collection_num)

    return df

def create_metadata_project_indicator(df, api_key, collection_num):
	"""
	Create-only version of create_edit_metadata_project_indicator.

	Creates new timeseries projects for indicators that don't already exist in the collection.
	Uses get_exist_meta_id_across_collections so an empty draft collection won't raise an
	exception. Already-existing indicators are skipped (no update performed).
	"""
	exist_id = get_exist_meta_id_across_collections(api_key, "timeseries", [collection_num])

	id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in df.columns), None)

	new_indices = []

	for index, row in df.iterrows():
		if row["INDICATOR"] in exist_id:
			df.loc[index, "numid"] = exist_id[row["INDICATOR"]]
			# log.info("Indicator project already exists, skipping creation: %s", row["INDICATOR"])
			print(f"Indicator project already exists, skipping creation: {row['INDICATOR']}")
		else:
			json_data = gen_metadata_payloads(row, id_column)
			df.loc[index, "numid"] = create_project(json_data, api_key, "timeseries").get("idno")
			new_indices.append(index)
			# log.info("New indicator metadata project created for %s", row["INDICATOR"])
			print(f"New indicator metadata project created for {row['INDICATOR']}")

	if new_indices:
		add_data360_admin_metadata(df.loc[new_indices], api_key)

	add_project_to_collection(df, api_key, collection_num)

	return df

def create_metadata_project_database(df, api_key, collection_num):
	"""
	Create-only version of create_edit_metadata_project_database.

	Creates new timeseries-db projects for datasets that don't already exist in the collection.
	Uses get_exist_meta_id_across_collections so an empty draft collection won't raise an
	exception. Already-existing dataset projects are skipped (no update performed).
	"""
	exist_id = get_exist_meta_id_across_collections(api_key, "timeseries-db", [collection_num])

	id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in df.columns), None)
	if id_column is None:
		raise ValueError("Neither 'DATABASE_ID' nor 'DATASET_ID' found in DataFrame columns.")

	name_column = next((col for col in ["DATABASE_NAME", "DATASET_NAME"] if col in df.columns), None)

	new_indices = []

	for index, row in df.iterrows():
		if row[id_column] in exist_id:
			df.loc[index, "numid"] = exist_id[row[id_column]]
			# log.info("Database project already exists, skipping creation: %s", row[id_column])
			print(f"Database project already exists, skipping creation: {row[id_column]}")
		else:
			json_data = gen_metadata_payloads_database(row, id_column, name_column)
			response = create_project(json_data, api_key, "timeseries-db")
			df.loc[index, "numid"] = response.get("idno")
			new_indices.append(index)
			# log.info("New database metadata project created for %s", row[id_column])
			print(f"New database metadata project created for {row[id_column]}")

	if new_indices:
		add_data360_admin_metadata(df.loc[new_indices], api_key)

	add_project_to_collection(df, api_key, collection_num)

	return df

def update_metadata_project_indicator(df, api_key, metadata_stage, draft_collection_num, prod_collection_num):
    """
    Update-only version of create_edit_metadata_project_indicator for the new staged-collection workflow.

    Unlike create_edit_metadata_project_indicator, this function never auto-creates projects.
    All timeseries projects must already exist in the Metadata Editor.
    If any are missing the pipeline fails immediately with a list of the missing idnos.

    Both QA and PROD runs check both draft and prod collections — projects always start in draft
    and are only moved to prod during the PROD publish run.
    """
    check_collections = [draft_collection_num, prod_collection_num]
    # log.info(
    #     "checking collections %s (draft) and %s (prod) for existing indicator projects",
    #     draft_collection_num, prod_collection_num,
    # )
    print(
        f"checking collections {draft_collection_num} (draft) and {prod_collection_num} (prod) for existing indicator projects"
    )

    exist_id = get_exist_meta_id_across_collections(api_key, "timeseries", check_collections)

    id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in df.columns), None)

    missing = [row["INDICATOR"] for _, row in df.iterrows() if row["INDICATOR"] not in exist_id]
    if missing:
        missing_list = ", ".join(missing)
        # log.error(
        #     "Missing indicator metadata projects: %s — "
        #     "projects must be pre-created in the Metadata Editor before running the publish pipeline.",
        #     missing_list,
        # )
        print(
            f"Missing indicator metadata projects: {missing_list} — "
            "projects must be pre-created in the Metadata Editor before running the publish pipeline."
        )
        raise RuntimeError(
            f"Publish pipeline aborted: {len(missing)} missing indicator project(s) — {missing_list}."
        )

    for index, row in df.iterrows():
        # stamp_version=False: this is a routine update of an already-existing project —
        # series_description.version_statement.version_date is curator-owned and must not be
        # overwritten by every pipeline run.
        json_data = gen_metadata_payloads(row, id_column, stamp_version=False)
        # log.info("Metadata payloads created for %s", row["INDICATOR"])
        print(f"Metadata payloads created for {row['INDICATOR']}")
        df.loc[index, "numid"] = exist_id[row["INDICATOR"]]
        update_project(json_data, api_key, exist_id[row["INDICATOR"]], "timeseries", True)
        # log.info("Metadata project partial updated for %s", row["INDICATOR"])
        print(f"Metadata project partial updated for {row['INDICATOR']}")
        geo_exist_boolean = check_geo_unit(exist_id[row["INDICATOR"]], api_key, "timeseries")
        patch_json = gen_metadata_patch(row, geo_exist_boolean)
        update_patch(patch_json, api_key, exist_id[row["INDICATOR"]], "timeseries")
        # log.info("Metadata project patch updated for %s", row["INDICATOR"])
        print(f"Metadata project patch updated for {row['INDICATOR']}")

    return df

def update_metadata_project_database(df, api_key, metadata_stage, draft_collection_num, prod_collection_num):
    """
    Update-only version of create_edit_metadata_project_database for the new staged-collection workflow.

    Unlike create_edit_metadata_project_database, this function never auto-creates projects.
    All timeseries-db projects must already exist in the Metadata Editor.
    If any are missing the pipeline fails immediately with a list of the missing idnos.

    Both QA and PROD runs check both draft and prod collections — projects always start in draft
    and are only moved to prod during the PROD publish run.
    """
    check_collections = [draft_collection_num, prod_collection_num]
    print(
        f"checking collections {draft_collection_num} (draft) and {prod_collection_num} (prod) for existing database projects"
    )
    # log.info(
    #     "checking collections %s (draft) and %s (prod) for existing database projects",
    #     draft_collection_num, prod_collection_num,
    # )

    exist_id = get_exist_meta_id_across_collections(api_key, "timeseries-db", check_collections)

    id_column = next((col for col in ["DATABASE_ID", "DATASET_ID"] if col in df.columns), None)
    if id_column is None:
        raise ValueError("Neither 'DATABASE_ID' nor 'DATASET_ID' found in DataFrame columns.")

    name_column = next((col for col in ["DATABASE_NAME", "DATASET_NAME"] if col in df.columns), None)

    missing = [row[id_column] for _, row in df.iterrows() if row[id_column] not in exist_id]
    if missing:
        missing_list = ", ".join(missing)
        print(
            f"Missing database metadata projects: {missing_list} — "
            "projects must be pre-created in the Metadata Editor before running the publish pipeline."
        )
        # log.error(
        #     "Missing database metadata projects: %s — "
        #     "projects must be pre-created in the Metadata Editor before running the publish pipeline.",
        #     missing_list,
        # )
        raise RuntimeError(
            f"Publish pipeline aborted: {len(missing)} missing database project(s) — {missing_list}."
        )

    for index, row in df.iterrows():
        # stamp_version=False: this is a routine update of an already-existing project —
        # database_description.version[0].date is curator-owned and must not be overwritten
        # by every pipeline run.
        json_data = gen_metadata_payloads_database(row, id_column, name_column, stamp_version=False)
        # log.info("Metadata payloads created for %s", row[id_column])
        print(f"Metadata payloads created for {row[id_column]}")
        df.loc[index, "numid"] = exist_id[row[id_column]]
        update_project(json_data, api_key, exist_id[row[id_column]], "timeseries-db", True)
        # log.info("Metadata project partial updated for %s", row[id_column])
        print(f"Metadata project partial updated for {row[id_column]}")
        geo_exist_boolean = check_geo_unit(exist_id[row[id_column]], api_key, "timeseries-db")
        patch_json = gen_metadata_patch_database(row, geo_exist_boolean, stamp_version=False)
        update_patch(patch_json, api_key, exist_id[row[id_column]], "timeseries-db")
        # log.info("Metadata project patch updated for %s", row[id_column])
        print(f"Metadata project patch updated for {row[id_column]}")

    return df

# Helper: find a collection whose title, split on ":" and taking the part before the
# first colon (stripped), exactly matches dataset_id. This avoids false positives from
# startswith matching (e.g. "WB_LPI" matching an existing "WB_LPI_20: ..." collection).
def find_dataset_collection(
		api_key, dataset_id,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	resp = requests.get(f"{meta_url}/api/collections", headers={"x-api-key": api_key})
	resp.raise_for_status()
	colls = resp.json()
	if isinstance(colls, dict):
		colls = colls.get("collections", [])
	return next(
		(c for c in colls if str(c.get("title", "")).split(":", 1)[0].strip() == dataset_id),
		None,
	)

def find_collection_exact(
		api_key, title,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	resp = requests.get(f"{meta_url}/api/collections", headers={"x-api-key": api_key})
	resp.raise_for_status()
	colls = resp.json()
	if isinstance(colls, dict):
		colls = colls.get("collections", [])
		
	return next((c for c in colls if str(c.get("title", "")) == title), None)

def create_collection(
		api_key, title, description="",
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	resp = requests.post(
		f"{meta_url}/api/collections",
		headers={"x-api-key": api_key, "Content-Type": "application/json"},
		json={"title": title, "description": description},
	)
	resp.raise_for_status()

def grant_admin_access(
		api_key, collection_id,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	for user_id in (4, 114, 91):
		resp = requests.post(
			f"{meta_url}/api/collections/user_project_access",
			headers={"x-api-key": api_key, "Content-Type": "application/json"},
			json={
				"collection_id": collection_id,
				"user_id":       user_id,
				"permissions":   "admin",
			},
		)
		resp.raise_for_status()
		print(f"  Admin access granted to user {user_id}.")

# Add new projects to the target collection resolved above.
# id_format is "id" (numeric database IDs), not "idno" — all_numids are numeric numid
# values, and remove_projects elsewhere has been confirmed to silently no-op when "idno"
# is declared for numeric IDs; kept consistent here even though add_projects tolerates it.
def add_projects_to_collection(
		api_key, dataset_collection_id, all_numids,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	resp = requests.post(
		f"{meta_url}/api/collections/add_projects",
		headers={"x-api-key": api_key, "Content-Type": "application/json"},
		json={"collections": [dataset_collection_id], "id_format": "id", "projects": all_numids},
	)
	resp.raise_for_status()
	print(f"Added {len(all_numids)} projects to collection {dataset_collection_id}.")


def move_collection_to_another_collection(
		api_key, dataset_collection_id, draft_collection_num,
		meta_url: str='https://metadataeditor.worldbank.org/index.php'
	):
	resp = requests.post(
		f"{meta_url}/api/collections/move",
		headers={"x-api-key": api_key, "Content-Type": "application/json"},
		json={"source_id": dataset_collection_id, "target_id": draft_collection_num},
	)
	if resp.status_code == 200:
		print(f"Collection {dataset_collection_id} linked to draft collection {draft_collection_num}.")
	elif resp.status_code in (400, 409):
		print(f"Collection {dataset_collection_id} already linked to draft collection {draft_collection_num} — skipping.")
	else:
		resp.raise_for_status()


def _export_file(meta_url, obj_id, obj_name, headers, folder_json, folder_pdf):
    """Export JSON and PDF for a single metadata object (indicator or database)."""
    results = {"json": None, "pdf": None}

    try:
        json_url = f"{meta_url}/api/editor/json/{obj_id}?exclude_private_fields=1&admin_metadata=1"
        resp = requests.get(json_url, headers=headers)
        resp.raise_for_status()
        file_path = f"{folder_json}/{obj_name}.json"
        with open(file_path, "w") as f:
            json.dump(resp.json(), f)
        results["json"] = file_path
    except Exception as e:
        results["json"] = str(e)
        # log.error("JSON export failed for %s: %s", obj_name, e)
        print(f"JSON export failed for {obj_name}: {e}")

    try:
        gen_url = f"{meta_url}/api/editor/generate_pdf/{obj_id}?exclude_private_fields=1"
        requests.get(gen_url, headers=headers).raise_for_status()
        pdf_url = f"{meta_url}/api/editor/pdf/{obj_id}"
        pdf_path = f"{folder_pdf}/{obj_name}.pdf"
        with requests.get(pdf_url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(pdf_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        results["pdf"] = pdf_path
    except Exception as e:
        results["pdf"] = str(e)
        # log.error("PDF export failed for %s: %s", obj_name, e)
        print(f"PDF export failed for {obj_name}: {e}")

    return results


def export_metadata_db(
    meta_url: str,
    dataset_id: str,
    api_key: str,
    catalog_env: str,
    obs_conf_path: str,
    collection_num: int
):
    """
    Export JSON and PDF metadata files for all indicators and the dataset to the dropzone.

    Returns:
        Tuple of (export_results, json_exported, pdf_exported)
    """
    from databricks.sdk.runtime import dbutils

    root_folder = f"/Volumes/{catalog_env}_data360/volumes/data360-dropzone/{obs_conf_path}/datasets/{dataset_id}/metadata"
    folders = {
        "json": root_folder,
        "pdf": f"{root_folder}/download",
        "dataset_json": f"{root_folder}/dataset",
        "dataset_pdf": f"{root_folder}/dataset/download",
    }

    # log.info("Recreating metadata folders under %s", root_folder)
    print(f"Recreating metadata folders under {root_folder}")
    try:
        dbutils.fs.rm(root_folder, recurse=True)
    except Exception:
        pass
    for folder in folders.values():
        dbutils.fs.mkdirs(folder)

    # log.info("Fetching indicator metadata for %s...", dataset_id)
    print(f"Fetching indicator metadata for {dataset_id}...")
    df_indicators = get_meta_by_dataset_db(meta_url, dataset_id, api_key, "timeseries", collection_num)
    # log.info("Fetching database metadata for %s...", dataset_id)
    print(f"Fetching database metadata for {dataset_id}...")
    df_databases = get_meta_by_dataset_db(meta_url, dataset_id, api_key, "timeseries-db", collection_num)
    headers = {"x-api-key": api_key}

    export_results = {"json": [], "pdf": []}
    json_exported, pdf_exported = {}, {}

    for df, j_folder, p_folder in [
        (df_databases, folders["dataset_json"], folders["dataset_pdf"]),
        (df_indicators, folders["json"], folders["pdf"]),
    ]:
        for _, row in df.iterrows():
            obj_id = row["idno"]
            obj_name = row["index"]
            # log.info("Processing %s: %s", obj_name, obj_id)
            print(f"Processing {obj_name}: {obj_id}")
            result = _export_file(meta_url, obj_id, obj_name, headers, j_folder, p_folder)

            if isinstance(result["json"], str) and result["json"].endswith(".json"):
                export_results["json"].append(result["json"])
                json_exported[obj_name] = True
            else:
                json_exported[obj_name] = result["json"]

            if isinstance(result["pdf"], str) and result["pdf"].endswith(".pdf"):
                export_results["pdf"].append(result["pdf"])
                pdf_exported[obj_name] = True
            else:
                pdf_exported[obj_name] = result["pdf"]

            time.sleep(0.1)

    # log.info("Metadata export for dataset %s completed", dataset_id)
    print(f"Metadata export for dataset {dataset_id} completed")
    return export_results, json_exported, pdf_exported
	









