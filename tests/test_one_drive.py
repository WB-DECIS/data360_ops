import pytest
from pathlib import Path
import yaml
from data360_ops.github import load_token
from data360_ops.one_drive import get_token_with_username

root_path = Path.cwd()
creds_path = root_path / "one_drive.token"

@pytest.fixture(scope="session")
def get_credentials_onedrive():
    creds = {
        'client_id': load_token(creds_path, "CLIENT_ID"),
        'tenant_id': load_token(creds_path, "TENANT_ID"),
        'username': load_token(creds_path, "USERNAME"),
        'password': load_token(creds_path, "PASSWORD"),
    }
    return creds

@pytest.fixture(scope="session")
def get_params_onedrive():
    params_path = root_path / "systems_params.yml"
    with open(params_path, "r") as f:
        params = yaml.safe_load(f)
    
    onedrive_params = params['one_drive']
    return onedrive_params

class TestGetTokenWithUsername:
    def test_get_token_with_username(
            self, 
            get_credentials_onedrive,
            get_params_onedrive
        ):
        creds = get_credentials_onedrive
        params = get_params_onedrive
        token = get_token_with_username(
            authority_url=params['authority_url'],
            resource_url=params['resource_url'],
            scope=params['scope'],
            client_id=creds['client_id'],
            tenant_id=creds['tenant_id'],
            username=creds['username'],
            password=creds['password']
        )
        assert isinstance(token, dict)
        assert "access_token" in token

    def test_get_token_with_invalid_credentials(
            self, 
            get_params_onedrive
        ):
        # Test behavior with invalid credentials
        params = get_params_onedrive
        with pytest.raises(ValueError) as exc:
            token = get_token_with_username(
            authority_url=params['authority_url'],
            resource_url=params['resource_url'],
            scope=params['scope'],
            client_id="invalid_client_id",
            tenant_id="invalid_tenant_id",
            username="invalid_username",
            password="invalid_password"
        )
        assert str(exc.value).startswith("Unable to get authority configuration")