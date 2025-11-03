import pytest
from data360_ops.github import load_token

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