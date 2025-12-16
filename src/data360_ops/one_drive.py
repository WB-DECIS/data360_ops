import msal

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