from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

AUTH_FILE_NAME = "auth.json"
CONFIG_FILE_NAME = "config.toml"
IMAGE_CONFIG_FILE_NAME = "api-image.toml"
KEY_FIELD = "OPENAI_API_KEY"
FILE_BASE_URL_FIELD = "base_url"
FILE_API_KEY_FIELD = "api_key"
FILE_API_KEY_ENV_FIELD = "api_key_env"
IMAGE_KEY_ENV = "OPENAI_IMAGE_API_KEY"
IMAGE_BASE_URL_ENV = "OPENAI_IMAGE_BASE_URL"
GENERIC_KEY_ENV = "OPENAI_API_KEY"
GENERIC_BASE_URL_ENV = "OPENAI_BASE_URL"


@dataclass(frozen=True)
class ProviderConfig:
    api_key: str
    base_url: str
    codex_home: Path


def resolve_codex_home(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    env_path = os.environ.get("CODEX_HOME")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def resolve_image_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / IMAGE_CONFIG_FILE_NAME


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_toml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("rb") as handle:
        return tomllib.load(handle)


def load_provider_config(
    codex_home: Path,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
    api_key_env: str | None = None,
    base_url_env: str | None = None,
) -> ProviderConfig:
    explicit_key_present = api_key_override is not None or api_key_env is not None
    explicit_url_present = base_url_override is not None or base_url_env is not None
    if explicit_key_present or explicit_url_present:
        if not explicit_key_present or not explicit_url_present:
            raise ValueError(
                "Explicit provider override must include both an API key "
                "(--api-key or --api-key-env) and a base URL (--base-url or --base-url-env)."
            )
        api_key = resolve_explicit_value(
            direct_value=api_key_override,
            env_name=api_key_env,
            direct_option="--api-key",
            env_option="--api-key-env",
        )
        base_url = resolve_explicit_value(
            direct_value=base_url_override,
            env_name=base_url_env,
            direct_option="--base-url",
            env_option="--base-url-env",
        )
        return build_provider_config(api_key, base_url, codex_home, "explicit provider override")

    file_pair = load_optional_image_provider_config(resolve_image_config_path())
    if file_pair is not None:
        return build_provider_config(*file_pair, codex_home, f"{IMAGE_CONFIG_FILE_NAME} configuration")

    image_pair = resolve_environment_pair(IMAGE_KEY_ENV, IMAGE_BASE_URL_ENV, "image-specific")
    if image_pair is not None:
        return build_provider_config(*image_pair, codex_home, "image-specific environment variables")

    generic_pair = resolve_environment_pair(GENERIC_KEY_ENV, GENERIC_BASE_URL_ENV, "generic")
    if generic_pair is not None:
        return build_provider_config(*generic_pair, codex_home, "generic environment variables")

    return load_codex_provider_config(codex_home)


def resolve_explicit_value(
    direct_value: str | None,
    env_name: str | None,
    direct_option: str,
    env_option: str,
) -> str:
    if direct_value is not None and env_name is not None:
        raise ValueError(f"Use only one of {direct_option} or {env_option}.")
    if direct_value is not None:
        value = direct_value.strip()
        if not value:
            raise ValueError(f"{direct_option} must not be empty.")
        return value
    if env_name is None:
        raise ValueError(f"Provide either {direct_option} or {env_option}.")

    normalized_name = env_name.strip()
    if not normalized_name:
        raise ValueError(f"{env_option} must name a non-empty environment variable.")
    return resolve_named_environment_value(normalized_name, env_option)


def resolve_named_environment_value(env_name: str, source: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise ValueError(f"Environment variable '{env_name}' named by {source} is empty or not set.")
    return value


def load_optional_image_provider_config(path: Path) -> tuple[str, str] | None:
    if not path.exists():
        return None

    config = load_toml(path)
    base_url = read_optional_string_field(config, FILE_BASE_URL_FIELD, path)
    api_key = read_optional_string_field(config, FILE_API_KEY_FIELD, path)
    api_key_env = read_optional_string_field(config, FILE_API_KEY_ENV_FIELD, path)
    if not base_url and not api_key and not api_key_env:
        return None
    if not base_url:
        raise ValueError(
            f"{path} must set '{FILE_BASE_URL_FIELD}' when a file API key is configured."
        )
    if api_key:
        return api_key, base_url
    if not api_key_env:
        # A URL without either key field does not activate this provider layer.
        return None

    return resolve_named_environment_value(
        api_key_env,
        f"'{FILE_API_KEY_ENV_FIELD}' in {path}",
    ), base_url


def read_optional_string_field(config: dict, field: str, path: Path) -> str:
    value = config.get(field)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"'{field}' in {path} must be a string.")
    return value.strip()


def resolve_environment_pair(
    key_env: str,
    base_url_env: str,
    label: str,
) -> tuple[str, str] | None:
    key_present = key_env in os.environ
    base_url_present = base_url_env in os.environ
    if not key_present and not base_url_present:
        return None
    if not key_present or not base_url_present:
        missing = base_url_env if key_present else key_env
        raise ValueError(
            f"The {label} provider environment variables must be set as a pair; missing {missing}."
        )

    api_key = os.environ[key_env].strip()
    base_url = os.environ[base_url_env].strip()
    if not api_key:
        raise ValueError(f"Environment variable '{key_env}' is empty.")
    if not base_url:
        raise ValueError(f"Environment variable '{base_url_env}' is empty.")
    return api_key, base_url


def load_codex_provider_config(codex_home: Path) -> ProviderConfig:
    auth_path = codex_home / AUTH_FILE_NAME
    config_path = codex_home / CONFIG_FILE_NAME
    auth = load_json(auth_path)
    api_key = auth.get(KEY_FIELD)
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError(f"{KEY_FIELD} is missing or empty in {auth_path}")

    config = load_toml(config_path)
    provider_name = config.get("model_provider")
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise ValueError(f"model_provider is missing in {config_path}")
    providers = config.get("model_providers", {})
    provider = providers.get(provider_name)
    if not isinstance(provider, dict):
        raise ValueError(f"Provider '{provider_name}' is missing in {config_path}")
    base_url = provider.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(f"base_url is missing for Provider '{provider_name}' in {config_path}")
    return build_provider_config(api_key, base_url, codex_home, "Codex provider configuration")


def build_provider_config(
    api_key: str,
    base_url: str,
    codex_home: Path,
    source: str,
) -> ProviderConfig:
    normalized_key = api_key.strip()
    if not normalized_key:
        raise ValueError(f"API key from {source} must not be empty.")
    return ProviderConfig(
        api_key=normalized_key,
        base_url=normalize_base_url(base_url, source),
        codex_home=codex_home,
    )


def normalize_base_url(base_url: str, source: str = "base_url") -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError(f"Base URL from {source} must not be empty.")
    if not normalized.startswith(("http://", "https://")):
        raise ValueError(f"Base URL from {source} must start with http:// or https://.")
    return normalized
