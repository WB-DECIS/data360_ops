
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