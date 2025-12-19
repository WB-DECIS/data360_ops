import msal
import requests

def get_token_with_username(
		authority_url: str, 
		resource_url: str, 
        scope: str,
		client_id: str,
		tenant_id: str,
		username: str,
		password: str
	) -> dict:
    """Gets token after authentication to Azure Active Directory (ADD) using MSAL

    Args:
        authority_url (str): string with the url to authenticate
        resource_url (str): graph api url
        scope (str): scope
		client_id (str): client id of the application
		tenant_id (str): tenant id of the application
		username (str): username for authentication
		password (str): password for authentication
    Returns:
        Dictionary with authentication tokens and other relevant information
    """
    app = msal.PublicClientApplication(
        client_id=client_id, 
        authority=f"{authority_url}{tenant_id}")
    
    token = app.acquire_token_by_username_password(
        username=username, 
		password=password,        
        scopes=[f"{resource_url}{scope}"])

    return token


def download_file(
		resource_url: str,
		api_version: str,
		site_user_id: str,
		file_path: str,
		output_filename: str,
		headers: dict,
		host_name: str = None, # type: ignore
		personal_drive: bool = False
	):
	"""This function downloads a file from OneDrive given the parameters.
	
	Args:
		resource_url (str): Graph API resource URL
		api_version (str): API version
		scope (str): Scope for authentication
		host_name (str): SharePoint host name
		site_user_id (str): User ID of the OneDrive site
		file_path (str): Path to the file in OneDrive
		output_filename (str): Local output filename
		headers (dict): Headers for authentication
		personal_drive (bool): Whether the file is in a personal drive or not. Default is False.
	Returns:
		None
	"""
	# Conditional to know where the file is stored
	# This is needed because the API endpoint is different
	if personal_drive:
		# This option is for personal drives

		# Download file
		download_url = (
			f"{resource_url}{api_version}/"
			f"users/{site_user_id}/drive/root:/{file_path}:/content"
		)
	else:
		# This options is for Team drive such as 'efiosfiles'

		# Throw error if host_name is not provided
		if host_name is None:
			raise ValueError("host_name must be provided for shared drives.")
		
		# Get ID of the drive
		site = requests.get(
			f"{resource_url}{api_version}/sites/{host_name}:/sites/{site_user_id}:/drive",
			headers=headers
		).json()

		drive_id = site['id']

		# Download file
		download_url = (
			f"{resource_url}{api_version}/"
			f"drives/{drive_id}/root:/{file_path}:/content"
		)
	# End if

	# Download the file
	response = requests.get(download_url, headers=headers)
	response.raise_for_status()

	# Export the file
	try:
		with open(f"{output_filename}", "wb") as f:
			f.write(response.content)
		success = True
		print(f"File downloaded successfully: {output_filename}")
	except Exception as e:
		print(f"Error downloading file: {e}")
		success = False
	
	return success


def list_files(
        resource_url: str,
		api_version: str,
		site_user_id: str,
		folder_path: str,
		headers: dict,
		host_name: str = None, # type: ignore
		personal_drive: bool = False
	) -> dict:
	"""This function downloads a file from OneDrive given the parameters.
	
	Args:
		resource_url (str): Graph API resource URL
		api_version (str): API version
		site_user_id (str): User ID of the OneDrive site
		folder_path (str): Path to the folder in OneDrive
		headers (dict): Headers for authentication
		host_name (str): SharePoint host name
		personal_drive (bool): Whether the file is in a personal drive or not. Default is False.
	
	Raises:
		ValueError: If no files are found in the specified folder.
		
	Returns:
		Dict: Dictionary with file/folder names as keys and their IDs as values
	"""
	# Conditional to know where the file is stored
	# This is needed because the API endpoint is different
	if personal_drive:
		# This option is for personal drives

		# Define URL
		url = (
			f"{resource_url}{api_version}/"
			f"users/{site_user_id}/drive/root:/{folder_path}:/children"
		)
	else:
		# This options is for Team drive such as 'efiosfiles'

		# Throw error if host_name is not provided
		if host_name is None:
			raise ValueError("host_name must be provided for shared drives.")
		
		# Get ID of the drive
		site = requests.get(
			f"{resource_url}{api_version}/"
			f"sites/{host_name}:/sites/{site_user_id}:/drive",
			headers=headers
		).json()

		drive_id = site['id']

		# Download file
		url = (
			f"{resource_url}{api_version}/"
			f"drives/{drive_id}/root:/{folder_path}:/children"
		)
	# End if

	# Request list of files
	response = requests.get(url, headers=headers)
	response.raise_for_status()

	# Extract list of files and folders
	if response.json()['value']:
		dir_dict = {}
		for x in response.json()['value']:
			dir_dict[x['name']] = x['id']
		return dir_dict
	else: 
		raise ValueError("No files found in the specified folder.")
