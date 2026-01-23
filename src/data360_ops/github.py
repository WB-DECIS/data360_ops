import requests
import time

def load_token(file_path, key="WB_DECIS_TOKEN"):
	"""Function to load a token from a file given a specific key.

	Args:
		file_path (str): Path to the file containing the token.
		key (str): The key associated with the desired token. Default is "WB_DECIS_TOKEN".
	Returns:
		str: The token value associated with the provided key.
	Raises:
		FileNotFoundError: If the specified file does not exist.
		ValueError: If the key is not found in the file.
	"""
	try:
		with open(file_path, "r") as f:
			for line in f:
				if "=" in line:
					temp_key, value = line.strip().split("=", 1)
					if temp_key.strip() == key:
						return value.strip()
		raise ValueError("The token key you provided was not found")
	except FileNotFoundError as e:
		raise FileNotFoundError(f"File not found... {e}")
	

def extract_list_dataset_ids(
		token: str,
		owner: str="worldbank",
		repo: str="data360-pipelines-databricks",
		label: str="Dataset"
	) -> set:
	"""Function to get a set of dataset IDs from GitHub issues in a repo that 
	have the specified label.
	
	Args:
		token (str): Personal access token for GitHub API authentication.
		owner (str): GitHub repository owner.
		repo (str): GitHub repository name.
		label (str): Label to filter issues by (default is "Dataset").
	Returns:
		set: A set of unique dataset IDs extracted from issue titles.
	"""
	# Set up headers with the token
	headers = {
		"Authorization": f"Bearer {token}",
		"Accept": "application/vnd.github+json",
	}

	# GitHub API endpoint (example: get authenticated user info)
	url = f"https://api.github.com/repos/{owner}/{repo}/issues"	

	# params
	params = {
		"state": "all",  # Options: open, closed, all
		"per_page": 100,  # Number of results per page (max 100)
		"page": 1,       # Page number to retrieve
	}

	# Iterate through pages
	print("Retrieving issues from GitHub...")
	all_issues = []
	while True:
		response = requests.get(url, headers=headers, params=params)
		if response.status_code != 200:
			raise ValueError(f"Failed to retrieve issues. Please check your token and repository are spelled correctly. Status code: {response.status_code}")
		issues = response.json()
		if not issues:
			break

		all_issues.extend(issues)
		params["page"] += 1
		time.sleep(1)  # To avoid hitting rate limits

	# Filter only issues with label "dataset"
	dataset_issues = [issue for issue in all_issues if 
					any(labels['name'] == label for labels in 
					issue.get('labels', []))]
	
	# Extract unique dataset ids
	print("Extracting dataset IDs from issues...")
	dataset_ids = set()
	for issue in dataset_issues:
		# Extract title
		title = issue.get('title', '')
		# Extract dataset id from title
		dataset_id = title.split(']')[0].strip("[")
		# Add to set
		dataset_ids.add(dataset_id)
	return dataset_ids
	

def create_issues(
		dataset_id: str,
		dataset_name: str,
		token: str,
		owner: str="worldbank",
		repo: str="data360-pipelines-databricks"
	) -> list:
	"""Function to create GitHub issues for a dataset in a specified repo.

	This function creates issues based on the a predefined structure for dataset.

	Args:
		dataset_id (str): Dataset identifier.
		dataset_name (str): Dataset name.
		token (str): Personal access token for GitHub API authentication.
		owner (str): GitHub repository owner.
		repo (str): GitHub repository name.

	Returns:
		list: A list of created issues with their details.
	"""
	# Set up headers with the token
	headers = {
		"Authorization": f"Bearer {token}",
		"Accept": "application/vnd.github+json",
	}

	# GitHub API endpoint to create issues
	url = f"https://api.github.com/repos/{owner}/{repo}/issues"

	# Define issue list with details
	issues_list = [
		{
			"title": f"[{dataset_id}] - {dataset_name}",
			"labels": ["Dataset"]
		},
		{
			"title": f"[{dataset_id}] - Collection module - Developer",
			"labels": ["Collection", "Task"],
			"body": "- [ ] Create Databricks Asset Bundle from template\n- [ ] Develop collection logic to harvest all data (notebook inside `inputs/working_file` folder)\n- [ ] Initial preprocess (long format)\n- [ ] Store raw data and data dictionary (list of indicators) in defined location (possibly DDH)\n- [ ] Share list of indicator details (data and metadata available) with Curator\n- [ ] Implement/Document collection function (API, File) in the `fetch_raw` notebook inside `pipeline_tasks` folder\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Data modeling - Curator",
			"labels": ["Modeling", "Task"],
			"body": "- [ ] Evaluation of the data to identify dimensionality, attributes and collapsing options.\n- [ ] Re-modeling design to comply with the established standards (DSDs, codelists, etc.)\n- [ ] Document finalized dimensions and items code(s) and name(s) in the template.\n\nTo perform this task, create a copy of this template [00. MAPPING_TEMPLATE.xlsx](https://worldbankgroup.sharepoint.com/:x:/r/sites/EFIOSFiles/Shared%20Documents/WB-Corporate/Data-Bank/Data360/DEC/Data%20Management/Mappings/00.%20MAPPING_TEMPLATE.xlsx?d=wa884911aa56c49a2886db6d4f8bf5735&csf=1&web=1&e=09ojHO&xsdata=MDV8MDJ8fGE5YTJkODRkZTE3MzRhYmZjMzM2MDhkZTI3YTg1NWJlfDMxYTJmZWMwMjY2YjRjNjdiNTZlMjc5NmQ4ZjU5YzM2fDB8MHw2Mzg5OTE4MDEwNzk3NDgxODF8VW5rbm93bnxWR1ZoYlhOVFpXTjFjbWwwZVZObGNuWnBZMlY4ZXlKRFFTSTZJbFJsWVcxelgwRlVVRk5sY25acFkyVmZVMUJQVEU5R0lpd2lWaUk2SWpBdU1DNHdNREF3SWl3aVVDSTZJbGRwYmpNeUlpd2lRVTRpT2lKUGRHaGxjaUlzSWxkVUlqb3hNWDA9fDF8TDJOb1lYUnpMekU1T2pVME5HWmtaRGt3WVRZME9UUTFZMk5pTldOaVpHTXdOek14TlRreVlqbGxRSFJvY21WaFpDNTJNaTl0WlhOellXZGxjeTh4TnpZek5UZ3lNRGszTURVMXw3OGNkM2ZiNDliYWU0ZTMzMjYzYTA4ZGUyN2E4NTViZXw0MDk3NDg2NWNkMDM0ODc0YThlNGVmMDk2MGY5ODAyOA%3D%3D&sdata=Z3FzaUk1LzBrQWtkNGpwWXVWbjB5SWhwcDd1OUpreHkvdVpvOWFOM3dhbz0%3D&ovuser=31a2fec0-266b-4c67-b56e-2796d8f59c36%2Cdgilsanchez%40worldbank.org), complete the modeling documentation and deposit the new file in this [location](https://worldbankgroup.sharepoint.com/sites/EFIOSFiles/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FEFIOSFiles%2FShared%20Documents%2FWB%2DCorporate%2FData%2DBank%2FData360%2FDEC%2FData%20Management%2FMappings&xsdata=MDV8MDJ8fGE5YTJkODRkZTE3MzRhYmZjMzM2MDhkZTI3YTg1NWJlfDMxYTJmZWMwMjY2YjRjNjdiNTZlMjc5NmQ4ZjU5YzM2fDB8MHw2Mzg5OTE4MDEwNzk3NzMzMjl8VW5rbm93bnxWR1ZoYlhOVFpXTjFjbWwwZVZObGNuWnBZMlY4ZXlKRFFTSTZJbFJsWVcxelgwRlVVRk5sY25acFkyVmZVMUJQVEU5R0lpd2lWaUk2SWpBdU1DNHdNREF3SWl3aVVDSTZJbGRwYmpNeUlpd2lRVTRpT2lKUGRHaGxjaUlzSWxkVUlqb3hNWDA9fDF8TDJOb1lYUnpMekU1T2pVME5HWmtaRGt3WVRZME9UUTFZMk5pTldOaVpHTXdOek14TlRreVlqbGxRSFJvY21WaFpDNTJNaTl0WlhOellXZGxjeTh4TnpZek5UZ3lNRGszTURVMXw3OGNkM2ZiNDliYWU0ZTMzMjYzYTA4ZGUyN2E4NTViZXw0MDk3NDg2NWNkMDM0ODc0YThlNGVmMDk2MGY5ODAyOA%3D%3D&sdata=NjdxYUQ0bW02aUVhdUpCbjdMVzNGeTF5U1lhcitEMGE2Sjg0cUVndGNUOD0%3D&ovuser=31a2fec0-266b-4c67-b56e-2796d8f59c36%2Cdgilsanchez%40worldbank.org) \n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["lcorsof"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Metadata elements creation - Curator",
			"labels": ["Metadata elements", "Task"],
			"body": "- [ ] Structural metadata: Update/upload artifacts in FMR\n- [ ] Referential metadata: Create indicator and dataset projects in metadata editor\n- [ ] Send notification to data owners that all projects have been created in the Metadata Editor\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["lcorsof"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Processing module - Developer",
			"labels": ["Processing", "Task"],
			"body": "- [ ] In the `transform_to_sdmx` notebook:\n    - [ ] Implement specifications for transformations (collapsing and new columns)\n    - [ ] Store processed data (Silver)\n- [ ] In the `validate_against_dsd` notebook:\n    - [ ] Structural validation \n    - [ ] Store processed data (Gold)\n- [ ] Create new notebook for aggregates (optional)\n    - [ ] Document how aggregation is going to be calculated (methodology, weights, etc)\n    - [ ] Calculation of aggregation based on needs\n- [ ] Content validation (optional)\n    - [ ] Implement hard check validation\n    - [ ] Create report about (hard check) validation\n    - [ ] Implement automatic (code) tests and log results\n- [ ] Test processing system (In QA) and create PR\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Pipeline to prod - Lead/Operations",
			"labels": ["Pip. to prod", "Task"],
			"body": "- [ ] PR Review: Testing custom tasks until validation.\n- [ ] Enable `publish_pipeline`\n- [ ] Merge pipeline branch to `main` branch\n- [ ] Push Asset Bundle to Databricks Prod\n- [ ] Change FMR_ENV to \"prod\" in the job parameters section\n- [ ] Run pipeline manually and push data to QA/Staging\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["gauravcusp"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Referential Metadata review - Metadata manager",
			"labels": ["Metadata review", "Task"],
			"body": "- [ ] Ensure referential metadata is ingested\n- [ ] Request to Focal Point or Data Requestor to gather their inputs on missing fields or improvement in ME projects\n- [ ] Apply or request to Focal Point or Data Requestor to assign tags to indicators.\n\nTo perform this task you may need some information from the data request, you can find it [here](https://worldbankgroup-my.sharepoint.com/:x:/g/personal/pmuthukumar1_worldbank_org/IQC5gJ59b_NGRayvneKMJ_KSARG7PBvx513sWDB5gQ37uuA?email=cmachingauta%40worldbank.org&e=0iCdsl) (you should have access, if not ask Lorena for it).\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["cmachingauta"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Data and Metadata Approval - Curator",
			"labels": ["Meta-data approval", "Task"],
			"body": "- [ ] Request for approval from Data Requestor or Focal Point\n- [ ] Document response in GitHub\n- [ ] Data AND metadata approved?\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["lcorsof"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Schedule pipeline - Lead/Operations",
			"labels": ["Ops", "Task"],
			"body": "In this task everything should be in production: Datalake, Databricks prod, Front-end prod, etc.\n\n- [ ] Evaluate embargo and apply it.\n- [ ] Trigger change from staging to prod.\n- [ ] Schedule pipeline\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["gauravcusp"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Maintenance - Lead/Operations",
			"labels": ["Maintenance", "Task"],
			"body": "Create subissues every time there's something wrong with the pipeline. Tag them as \"Subtask\" and \"Maintenance\"\n\n**Note: When adding comments, please add as a title the item that you are referring to. Example:**\n```\n# [Item title]\n\n[Your comment, e.g., This was done locally and ...]\n```\n",
			"assignees": ["gauravcusp"],
			"type": "Task",
		},
	]

	# Initialize list to store created issues
	created_issues = []

	# Adding issues to repo
	for issue in issues_list:
		print(f'{issue["title"]} - {issue["labels"]}')
		# Create issue
		response = requests.post(url, headers=headers, json=issue)

		# Check the response
		if response.status_code in [200, 201]:
			print("Issue created successfully!")
			# print(response.json())
			issue["id"] = response.json().get("id")
			issue["node_id"] = response.json().get("node_id")
			issue["number"] = response.json().get("number")
			# print(f"Issue number: {issue["issue_number"]}")
			created_issues.append(issue)
		else:
			print(f"Could not create issue: {response.status_code}")
			print(response.text)
		time.sleep(0.1)
	# End for loop

	return created_issues


def add_subissues(
		created_issues: list, 
		token: str,
		owner: str="worldbank",
		repo: str="data360-pipelines-databricks"
	):
	"""Function to add sub-issues to created issues in a GitHub repo.

	This function add epics as sub-issues to dataset issue and tasks as sub-issues to epics.
	
	Args:
		created_issues (list): List of created issues with their details.
		token (str): Personal access token for GitHub API authentication.
		owner (str): GitHub repository owner.
		repo (str): GitHub repository name.
	Returns:
		Bool: True if sub-issues were added successfully, False otherwise.
	"""
	# Set up headers with the token
	headers = {
		"Authorization": f"Bearer {token}",
		"Accept": "application/vnd.github+json",
	}

	# Create subsets by tasks, epics and datasets labels
	datasets = [issue for issue in created_issues if "Dataset" in issue["labels"]]
	# epics = [issue for issue in created_issues if "Epic" in issue["labels"]]
	tasks = [issue for issue in created_issues if "Task" in issue["labels"]]

	# Extract dataset issue number
	dataset_issue_number = datasets[0]["number"]

	# GitHub API endpoint to add subissues to specified issue
	url = f"https://api.github.com/repos/{owner}/{repo}/issues/{dataset_issue_number}/sub_issues"

	# Assign tasks as sub-issues to dataset
	for task in tasks:
		print(f'Adding task {task["title"]} to dataset issue #{dataset_issue_number}')
		task_issue_id = task["id"]
		# params
		create_params = {
			"sub_issue_id": task_issue_id,
			"replace_parent": False,
		}
		# Make the request
		response = requests.post(url, headers=headers, json=create_params)

		# Check the response
		if response.status_code in [200, 201]:
			print("Subissue added successfully!")
			# print(response.json())
		else:
			print(f"Could not add issue: {response.status_code}")
			print(response.text)
		time.sleep(0.1)
	# End for loop through tasks

	return True


def add_dependencies(
		created_issues: list,
		token: str, 
		owner: str, 
		repo: str
	):
	"""Function to add dependencies to created issues in a GitHub repo.

	This function add dependencies between issues.
	
	Args:
		created_issues (list): List of created issues with their details.
		token (str): Personal access token for GitHub API authentication.
		owner (str): GitHub repository owner.
		repo (str): GitHub repository name.
	Returns:
		Bool: True if dependencies were added successfully, False otherwise.
	"""
	# Define order for dependencies
	# First element of the list won't have any dependencies
	tags = ['Modeling', 'Metadata elements', 'Processing', 'Pip. to prod', 
		 'Metadata review', 'Meta-data approval', 'Ops', 'Maintenance']

	# Set up headers with the token
	headers = {
		"Authorization": f"Bearer {token}",
		"Accept": "application/vnd.github+json",
	}

	# Create subsets by tasks, epics and datasets labels
	datasets = [issue for issue in created_issues if "Dataset" in issue["labels"]]
	# epics = [issue for issue in created_issues if "Epic" in issue["labels"]]
	tasks = [issue for issue in created_issues if "Task" in issue["labels"]]

	for i in range(len(tags)):
		tag = tags[i]
		if tag == 'Modeling':
			continue
		else:
			previous_tag = tags[i - 1]
			# Extract issue number based on tag and then the number
			issue_number = [i for i in tasks if tag in i['labels']][0]['number']
			# Extract previous issue id based on tag
			previous_issue_id = [i for i in tasks if previous_tag in i['labels']][0]['id']
			dependency_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/dependencies/blocked_by"
			params = {
				"issue_id": previous_issue_id
			}
			# Make the request
			response = requests.post(dependency_url, headers=headers, json=params)

			# Check the response
			if response.status_code in [200, 201]:
				print(f"{tag}: 'Blocked by' dependency added successfully!")
				# print(response.json())
			else:
				print(f"Could not add dependency: {response.status_code}")
				print(response.text)
			time.sleep(0.1)
		# End if
	# End for loop
	return True


def create_issues_for_dataset(
		dataset_id: str,
		dataset_name: str,
		token: str,
		owner: str="worldbank",
		repo: str="data360-pipelines-databricks"
	) -> None | bool:
	"""Function to create GitHub issues for a dataset if it does not already exist.

	This function is a wrapper that checks if a dataset ID already exists in the repo. If not, it creates the issues and sub-issues for the dataset.

	Args:
		dataset_id (str): Dataset identifier.
		dataset_name (str): Dataset name.
		token (str): Personal access token for GitHub API authentication.
		owner (str): GitHub repository owner.
		repo (str): GitHub repository name.
	Returns:
		None | bool: Returns True if issues were created, None if dataset ID already exists.
	"""
	print("Extracting the list of created datasets in the repo...")
	existing_dataset_ids = extract_list_dataset_ids(
		token=token,
		owner=owner,
		repo=repo,
		label="Dataset"
	)
	
	# Check if dataset_id already exists
	if dataset_id not in existing_dataset_ids:
		print(f"Creating issue for dataset ID {dataset_id}...")
		# Create issues
		issues = create_issues(
			dataset_id=dataset_id,
			dataset_name=dataset_name,
			token=token,
			owner=owner,
			repo=repo
		)

		# Add subissues
		added = add_subissues(
			created_issues=issues,
			token=token,
			owner=owner,
			repo=repo
		)

		# Add dependencies
		dependencies = add_dependencies(
			created_issues=issues,
			token=token,
			owner=owner,
			repo=repo
		)

		return added
	else:
		print(f"Dataset ID {dataset_id} already exists. Skipping issue creation.")
		return None