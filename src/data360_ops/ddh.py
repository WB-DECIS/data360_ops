import wbddh
from databricks.sdk.runtime import dbutils
import requests

def trigger_update(
        dataset_id: str|list,
        ddh_params: dict,
        catalog_env: str,
        obs_conf: str,
        user_email: str,
        upload: str = 'both',
        indicator_id: str|list|bool = []
        ):
    """Triggers the update of the metadata/data file in the dropzone
    Args:
        dataset_id (str|list): list of dataset id (data360 dataset id)
        ddh_params (dict): dictionary with the parameters to connect to DDH
        ddh_env (str): environment to connect to DDH (e.g. 'ops' or 'ops_qa')
        user_email: user email (the email you want to receive the notification)
        upload (str): type of upload (data/metadata/both)
        indicator_id (dict|bool): Optional. List of indicator id 
            (data360 indicator id). If no input, then load the whole dataset.
        temp (bool): Force kedro execution order
    :return: response
    """
    # Check if dataset_id is a string to convert it to a list
    if isinstance(dataset_id, str):
        dataset_id = [dataset_id]

    if catalog_env == "dev" or catalog_env == "qa":
        ddh_catalog_env = "ops_qa"
    elif catalog_env == "prd":
        ddh_catalog_env = "ops"
    else:
        raise ValueError(f"Invalid catalog_environment: {catalog_env}")

    # Get DDH params for the environment of interest
    ddh_params = ddh_params[ddh_catalog_env]
    # log.info("DDH params: %s", ddh_params)
    print(f"DDH params: {ddh_params}")

    # Get secrets for the environment of interest
    ddh_credentials = {
        "client_id": dbutils.secrets.get("data360-secret-scope", f"ddh-{catalog_env}-client-id"),
        "tenant_id": dbutils.secrets.get("data360-secret-scope", f"ddh-{catalog_env}-tenant-id"),
        "username": dbutils.secrets.get("data360-secret-scope", f"ddh-{catalog_env}-username"),
        "password": dbutils.secrets.get("data360-secret-scope", f"ddh-{catalog_env}-password"),
    }
    
    wbddh.set_api_host(ddh_params["resource"])
 
    params = {
        "authorityHostURL": ddh_params["authority_host"],
        "clientId": ddh_credentials["client_id"],
        "tenant": ddh_credentials["tenant_id"],
        "resourceURL": ddh_params["resource"],
        "username": ddh_credentials["username"],
        "password": ddh_credentials["password"],
        }

    try:
        session = wbddh.create_service_account_session(params=params)
        # log.info("DDH session created successfully")
        print("DDH session created successfully")
    except Exception as e:
        raise Exception(f"Failed to create DDH session: {str(e)}")
        return None

    body = {
        "indicators": indicator_id,
        "datasetIds": dataset_id,#.tolist(),
        "userEmail": user_email,
        "type": upload.lower(),
    }
    # log.info("DDH request body: %s", body)
    print(f"DDH request body: {body}")
    try:
        if obs_conf == "public":
            req_url = f"{ddh_params['api_host']}/{ddh_params['data_load_endpoint']}"
            # log.info("DDH request URL: %s", req_url)
            print(f"DDH request URL: {req_url}")
        elif obs_conf == "ouo":
            req_url = f"{ddh_params['api_host']}/{ddh_params['data_load_endpoint_ou']}"
            # log.info("DDH request URL: %s", req_url)
            print(f"DDH request URL: {req_url}")
        req = requests.post(req_url, json=body, headers=session.headers)
        
        return req.text

    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to trigger metadata update: {str(e)}")
        return None
