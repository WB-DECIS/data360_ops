import pytest
from pathlib import Path
import yaml
from data360_ops.github import load_token
from data360_ops.one_drive import (
    get_token_with_username,
    download_file,
    list_files
)

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


class TestDownloadFile:
    def test_download_file_success(
            self,
            get_credentials_onedrive,
            get_params_onedrive,
            tmp_path
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
        headers = {
            'Authorization': f"Bearer {token['access_token']}"
        }
        output_file = tmp_path / "TemplateMappingFile.xlsx"
        try:
            download_file(
                resource_url=params['resource_url'],
                api_version=params['api_version'],
                site_user_id=params['site_id'],
                file_path=params['template_mapping_file'],
                output_filename=str(output_file),
                headers=headers,
                host_name=params['sharepoint_host_name'],
                personal_drive=False
            )
            assert output_file.exists()
        finally:
            if output_file.exists():
                output_file.unlink()

    def test_download_file_invalid_path(
            self,
            get_credentials_onedrive,
            get_params_onedrive,
            tmp_path
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
        headers = {
            'Authorization': f"Bearer {token['access_token']}"
        }
        output_file = tmp_path / "NonExistentFile.xlsx"
        with pytest.raises(Exception) as exc:
            download_file(
                resource_url=params['resource_url'],
                api_version=params['api_version'],
                site_user_id=params['site_id'],
                file_path="non/existent/path.xlsx",
                output_filename=str(output_file),
                headers=headers,
                host_name=params['sharepoint_host_name'],
                personal_drive=False
            )
        assert "404 Client Error" in str(exc.value)

    
class TestListFiles:
    def test_list_files_success(
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
        headers = {
            'Authorization': f"Bearer {token['access_token']}"
        }
        files_dict = list_files(
            resource_url=params['resource_url'],
            api_version=params['api_version'],
            host_name=params['sharepoint_host_name'],
            site_user_id=params['site_id'],
            folder_path=params['mapping_file_path'],
            headers=headers,
            personal_drive=False
        )
        assert isinstance(files_dict, dict)
        assert len(files_dict) > 0

    def test_list_files_invalid_folder(
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
        headers = {
            'Authorization': f"Bearer {token['access_token']}"
        }
        with pytest.raises(Exception) as exc:
            files_dict = list_files(
                resource_url=params['resource_url'],
                api_version=params['api_version'],
                host_name=params['sharepoint_host_name'],
                site_user_id=params['site_id'],
                folder_path="non/existent/folder",
                headers=headers,
                personal_drive=False
            )
        assert "404 Client Error" in str(exc.value)