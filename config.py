import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_llm_config():
    return load_config().get("llm", {})


def get_memory_config():
    return load_config().get("memory", {})


def get_character_config():
    return load_config().get("character", {})


def get_feishu_config():
    return load_config().get("feishu", {})


def get_server_config():
    return load_config().get("server", {})


def get_search_config():
    return load_config().get("search", {
        "api_url": "http://localhost:9528/search",
        "api_key": "",
        "api_secret": "",
    })
