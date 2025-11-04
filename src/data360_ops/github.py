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
			"title": f"[{dataset_id}] - Collection module",
			"labels": ["Collection", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Data curation",
			"labels": ["Modeling", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Metadata elements creation",
			"labels": ["Metadata elements", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Processing module",
			"labels": ["Processing", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Pipeline integration",
			"labels": ["Pip. integration", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Pipeline to prod",
			"labels": ["Pip. to prod", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Referential metadata review",
			"labels": ["Metadata review", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Data and metadata approval",
			"labels": ["Meta-data approval", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Publication",
			"labels": ["Publishing", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Maintainance",
			"labels": ["Maintenance", "Epic"],
		},
		{
			"title": f"[{dataset_id}] - Harvesting",
			"labels": ["Collection", "Task"],
			"body": "- [ ] Implement/Document collection function (API, File)\n- [ ] Store raw data and data dictionary (list of indicators) in defined location (possibly DDH)\n- [ ] Share list of indicator details (data and metadata available) with Curator",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Data modelling",
			"labels": ["Modeling", "Task"],
			"body": "- [ ] Evaluation of the data to identify dimensionality, attributes and collapsing options.\n- [ ] Re-modeling design to comply with the established standards (DSDs, codelists, etc.)\n- [ ] Document finalized dimensions and items code(s) and name(s) in the template.",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Structural metadata: Process artifacts in FMR",
			"labels": ["Metadata elements", "Task"],
			"body": "- [ ] Process (update/upload) artifacts in FMR",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Referencial metadata: Create projects in metadata editor",
			"labels": ["Metadata elements", "Task"],
			"body": "- [ ] Create indicator and dataset metadata projects in Metadata Editor",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Send notification to data owners",
			"labels": ["Metadata elements", "Task"],
			"body": "- [ ] Send notification to data owners that all projects have been created in the Metadata Editor",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Implement specifications for transformations (collapsing and new columns)",
			"labels": ["Processing", "Task"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Implement/Document aggregation processing",
			"labels": ["Processing", "Task"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Store processed data (Silver)",
			"labels": ["Processing", "Task"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Structural validation",
			"labels": ["Processing", "Task"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Store processed data (Gold)",
			"labels": ["Processing", "Task"],
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Content validation",
			"labels": ["Processing", "Task"],
			"body": "- [ ] Implement hard check validation\n- [ ] Create report about (hard check) validation\n- [ ] Implement automatic (code) tests and log results",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Test processing system",
			"labels": ["Processing", "Task"],
			"body": "- [ ] Test processing system.\n- [ ] Create PR to main.",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - PR Review: Testing custom tasks until validation",
			"labels": ["Pip. integration", "Task"],
			"body": "- [ ] PR review: Testing custom tasks until validation (locally).",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Enable publish pipeline",
			"labels": ["Pip. integration", "Task"],
			"body": "- [ ] Apply instruments to ensure ingestion of finalized data into dissemination environment.\n- [ ] Prepopulate referencial metadata from mapping file to ME.\n- [ ] Create Indicators CSV files.\n- [ ] Create Download CSV files.\n- [ ] Export JSON and PDF metadata files.\n- [ ] Verify exported files.\n- [ ] Trigger publishing.",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Move pipeline to production",
			"labels": ["Pip. to prod", "Task"],
			"body": "- [ ] Push pipeline to prod in Databricks.\n- [ ] Initial pipeline execution to push data into PROD.",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Metadata review",
			"labels": ["Metadata review", "Task"],
			"body": "- [ ] Ensure referential metadata is ingested\n- [ ] Request to FP or DR to gather their inputs on missing fields or improvement in ME projects\n- [ ] Apply or request to FP or DR to assign tags to indicators.",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Data and metadata approval",
			"labels": ["Meta-data approval", "Task"],
			"body": "- [ ] Request for approval from DR or FP\n- [ ] Document response in GitHub\n- [ ] Data AND metadata approved?",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Move to Production",
			"labels": ["Publishing", "Task"],
			"body": "- [ ] Evaluate embargo and apply it.\n- [ ] Trigger change from staging to prod.\n- [ ] Schedule pipeline",
			"type": "Task",
		},
		{
			"title": f"[{dataset_id}] - Add pipeline to monitoring tool",
			"labels": ["Maintenance", "Task"],
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
	epics = [issue for issue in created_issues if "Epic" in issue["labels"]]
	tasks = [issue for issue in created_issues if "Task" in issue["labels"]]

	# Extract dataset issue number
	dataset_issue_number = datasets[0]["number"]

	# GitHub API endpoint to add subissues to specified issue
	url = f"https://api.github.com/repos/{owner}/{repo}/issues/{dataset_issue_number}/sub_issues"

	# Assign epics as sub-issues to dataset
	for epic in epics:
		print(f'Adding epic {epic["title"]} to dataset issue #{dataset_issue_number}')
		epic_issue_id = epic["id"]
		# params
		create_params = {
			"sub_issue_id": epic_issue_id,
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
	# End for loop through epics

	# Assign tasks as sub-issues to epics
	for epic in epics:
		# Extract issue number and primary label
		issue_number = epic["number"]
		label = [label for label in epic["labels"] if label != "Epic"][0]
		
		# Filter tasks that match the epic's primary label
		tasks_for_epic = [task for task in tasks if label in task["labels"]]

		# Update url for each epic
		url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/sub_issues"
		
		# Loop through tasks and assign to epic
		for task in tasks_for_epic:
			print(f'Adding epic {task["title"]} to epic issue #{issue_number} - label: {label}')
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
	# End for loop through epics

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

		return added
	else:
		print(f"Dataset ID {dataset_id} already exists. Skipping issue creation.")
		return None