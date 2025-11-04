import pytest
import os
from pathlib import Path
from data360_ops.github import (load_token, extract_list_dataset_ids)

@pytest.fixture(scope="session")
def local_token():
    token_path = Path.cwd() / "github.token"
    temp_token = load_token(token_path)
    return temp_token


class TestLoadToken:
    def test_load_token_default_key(self, tmp_path):
        # Test loading token with default key
        p = tmp_path / "env.txt"
        p.write_text("WB_DECIS_TOKEN=abc123\nOTHER=val\n")
        assert load_token(str(p)) == "abc123"

    def test_load_token_custom_key_and_whitespace(self, tmp_path):
        # Test loading token with custom key and surrounding whitespace
        p = tmp_path / "env.txt"
        p.write_text("  WB_DECIS_TOKEN = should_not_pick\nMY_KEY =  secret_value  \n")
        assert load_token(str(p), key="MY_KEY") == "secret_value"

    def test_load_token_value_with_equals(self, tmp_path):
        # Test loading token where value contains '=' characters
        p = tmp_path / "env.txt"
        p.write_text("COMPLEX=part1=part2=part3\n")
        assert load_token(str(p), key="COMPLEX") == "part1=part2=part3"

    def test_load_token_missing_file_raises(self):
        # Test that FileNotFoundError is raised for missing file
        missing = "non_existent_file.env"
        with pytest.raises(FileNotFoundError):
            load_token(missing)

    def test_load_token_key_not_found_raises(self, tmp_path):
        # Test that ValueError is raised when key is not found
        p = tmp_path / "env.txt"
        p.write_text("SOME_KEY=val\n")        
        with pytest.raises(ValueError) as exc:
            load_token(str(p), key="MISSING")
        assert str(exc.value) == "The token key you provided was not found"

    
class TestExtractListDatasetIds:
    def test_extract_list_dataset_ids(self, local_token):
        # Test extracting dataset IDs from GitHub issues
        dataset_ids = extract_list_dataset_ids(
            token=local_token,
            owner="WB-DECIS",
            repo="testing_issues",
            label="Dataset"
        )
        assert isinstance(dataset_ids, set)
        assert all(isinstance(did, str) for did in dataset_ids)
        assert "WB_TEST_4" in dataset_ids

    def test_extract_list_dataset_ids_no_datasets(self, local_token):
        # Test extracting dataset IDs when no issues with the label exist
        dataset_ids = extract_list_dataset_ids(
            token=local_token,
            owner="WB-DECIS",
            repo="testing_issues",
            label="NonExistentLabel"
        )
        assert dataset_ids == set()

    def test_extract_list_dataset_ids_invalid_token(self):
        # Test behavior with an invalid token
        with pytest.raises(ValueError) as exc:
            extract_list_dataset_ids(
                token="invalid_token",
                owner="WB-DECIS",
                repo="testing_issues",
                label="Dataset"
            )
        assert str(exc.value) == "Failed to retrieve issues. Please check your token and repository are spelled correctly. Status code: 401"

    def test_extract_list_dataset_ids_wrong_repo(self, local_token):
        # Test behavior with an invalid repo
        with pytest.raises(ValueError) as exc:
            extract_list_dataset_ids(
                token=local_token,
                owner="WB-DECIS",
                repo="wrong_repo",
                label="Dataset"
            )
        assert str(exc.value).startswith("Failed to retrieve issues. Please check your token and repository are spelled correctly.")

    def test_extract_list_dataset_ids_pagination(self, local_token):
        # Test pagination handling by using a repo with many issues
        dataset_ids = extract_list_dataset_ids(
            token=local_token,
            owner="WB-DECIS",
            repo="testing_issues",
            label="Epic"
        )
        assert isinstance(dataset_ids, set)
        assert len(dataset_ids) > 0

    def test_extract_list_dataset_ids_no_issues(self, local_token):
        # Test behavior when there are no issues in the repo
        with pytest.raises(ValueError) as exc:
            dataset_ids = extract_list_dataset_ids(
                token=local_token,
                owner="WB-DECIS",
                repo="empty_repo",
                label="Dataset"
            )
        assert str(exc.value).startswith("Failed to retrieve issues. Please check your token and repository are spelled correctly.")