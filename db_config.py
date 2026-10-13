"""
db_config.py
Saves and loads a dataset's database connection settings. The password
is encrypted (via crypto_utils) before ever touching disk — everything
else (host, port, table, column mapping) is stored as plain JSON since
none of it is secret on its own.
"""

import json
from pathlib import Path

from crypto_utils import encrypt_value, decrypt_value

CONFIG_FILENAME = "db_config.json"


def save_db_config(dataset_dir, db_type, host, port, database, username, password,
                    table, column_mapping):
    dataset_dir = Path(dataset_dir)
    config = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": username,
        "password_encrypted": encrypt_value(password) if password else "",
        "table": table,
        "column_mapping": column_mapping,
    }
    (dataset_dir / CONFIG_FILENAME).write_text(json.dumps(config, indent=2))


def load_db_config(dataset_dir):
    """Returns the config dict with password DECRYPTED, ready to use for
    a real connection — or None if no config has been saved yet."""
    path = Path(dataset_dir) / CONFIG_FILENAME
    if not path.exists():
        return None

    config = json.loads(path.read_text())
    config["password"] = decrypt_value(config["password_encrypted"]) if config["password_encrypted"] else ""
    del config["password_encrypted"]
    return config


def has_db_config(dataset_dir) -> bool:
    return (Path(dataset_dir) / CONFIG_FILENAME).exists()