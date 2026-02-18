import pandas as pd
from pymetadataeditor import MetadataEditor 
from .utils import extract_value_from_key

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
