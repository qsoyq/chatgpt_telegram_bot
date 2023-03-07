import os

from pathlib import Path

import dotenv
import yaml

if config_path := os.getenv("config_dir"):
    config_dir = Path(config_path)
else:
    config_dir = Path(__file__).parent.parent.resolve() / "config"

assert (config_dir / 'config.yml').exists(), config_dir.resolve()
assert (config_dir / 'config.env').exists(), config_dir.resolve()

# load yaml config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# load .env config
config_env = dotenv.dotenv_values(config_dir / "config.env")

# config parameters
telegram_token = config_yaml["telegram_token"] or config_env.get("telegram_token") or os.getenv("telegram_token", "")
openai_api_key = config_yaml["openai_api_key"] or config_env.get("openai_api_key") or os.getenv("openai_api_key", "")
use_chatgpt_api = config_yaml.get("use_chatgpt_api", True)
allowed_telegram_usernames = config_yaml["allowed_telegram_usernames"]
new_dialog_timeout = config_yaml["new_dialog_timeout"]
mongodb_uri = f"mongodb://mongo:{config_env['MONGODB_PORT']}"
