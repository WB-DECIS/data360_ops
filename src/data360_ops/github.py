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
	