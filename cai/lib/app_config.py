"""Application configuration entered via the Launchpad and persisted on disk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cai.lib.cai_common import write_dotenv_file
from cai.lib.paths import CONFIG_DIR

DEPLOYMENT_CONFIG_JSON = CONFIG_DIR / "deployment_config.json"
APP_ENVIRONMENT_ENV = CONFIG_DIR / "app_environment.env"

SECRET_KEYS: frozenset[str] = frozenset(
    {
        "ngc_api_key",
        "elevenlabs_api_key",
        "camb_api_key",
    }
)

# JSON field -> process environment variable
_ENV_MAP: dict[str, str] = {
    "nim_deploy_mode": "NIM_DEPLOY_MODE",
    "s2s_service": "S2S_SERVICE",
    "ngc_api_key": "NGC_API_KEY",
    "elevenlabs_api_key": "ELEVENLABS_API_KEY",
    "camb_api_key": "CAMB_API_KEY",
    "lipsync_nim_tags_selector": "LIPSYNC_NIM_TAGS_SELECTOR",
    "s2s_default_target_language": "S2S_DEFAULT_TARGET_LANGUAGE",
    "default_source_language": "DEFAULT_SOURCE_LANGUAGE",
    "default_target_language": "DEFAULT_TARGET_LANGUAGE",
    "lipsync_nvidia_function_id": "LIPSYNC_NVIDIA_FUNCTION_ID",
    "asd_nvidia_function_id": "ASD_NVIDIA_FUNCTION_ID",
    "nvidia_serverless_grpc_host": "NVIDIA_SERVERLESS_GRPC_HOST",
    "nvidia_serverless_grpc_port": "NVIDIA_SERVERLESS_GRPC_PORT",
    "reference_app_enable_preprocessing": "REFERENCE_APP_ENABLE_PREPROCESSING",
    "voice_name": "VOICE_NAME",
    "target_language_label": "TARGET_LANGUAGE_LABEL",
}


@dataclass
class AppConfig:
    """User configuration for Content Localization (Setup page)."""

    nim_deploy_mode: str = "SERVERLESS"
    s2s_service: str = "EL_DUBBING"
    ngc_api_key: str = ""
    elevenlabs_api_key: str = ""
    camb_api_key: str = ""
    lipsync_nim_tags_selector: str = "language=de"
    s2s_default_target_language: str = "de"
    default_source_language: str = "auto"
    default_target_language: str = "de"
    lipsync_nvidia_function_id: str = ""
    asd_nvidia_function_id: str = ""
    nvidia_serverless_grpc_host: str = "grpc.nvcf.nvidia.com"
    nvidia_serverless_grpc_port: str = "443"
    reference_app_enable_preprocessing: bool = False
    voice_name: str = ""
    target_language_label: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        preprocessing = data.get("reference_app_enable_preprocessing", False)
        if isinstance(preprocessing, str):
            preprocessing = preprocessing.strip().lower() in {"1", "true", "yes", "on"}
        target = str(data.get("default_target_language") or data.get("s2s_default_target_language") or "de")
        return cls(
            nim_deploy_mode=str(data.get("nim_deploy_mode", "SERVERLESS")).upper(),
            s2s_service=str(data.get("s2s_service", "EL_DUBBING")),
            ngc_api_key=str(data.get("ngc_api_key", "")),
            elevenlabs_api_key=str(data.get("elevenlabs_api_key", "")),
            camb_api_key=str(data.get("camb_api_key", "")),
            lipsync_nim_tags_selector=str(data.get("lipsync_nim_tags_selector", "language=de")),
            s2s_default_target_language=str(data.get("s2s_default_target_language", target)),
            default_source_language=str(data.get("default_source_language", "auto")),
            default_target_language=target,
            lipsync_nvidia_function_id=str(data.get("lipsync_nvidia_function_id", "")),
            asd_nvidia_function_id=str(data.get("asd_nvidia_function_id", "")),
            nvidia_serverless_grpc_host=str(
                data.get("nvidia_serverless_grpc_host", "grpc.nvcf.nvidia.com")
            ),
            nvidia_serverless_grpc_port=str(data.get("nvidia_serverless_grpc_port", "443")),
            reference_app_enable_preprocessing=bool(preprocessing),
            voice_name=str(data.get("voice_name", "")),
            target_language_label=str(data.get("target_language_label", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "nim_deploy_mode": self.nim_deploy_mode,
            "s2s_service": self.s2s_service,
            "ngc_api_key": self.ngc_api_key,
            "elevenlabs_api_key": self.elevenlabs_api_key,
            "camb_api_key": self.camb_api_key,
            "lipsync_nim_tags_selector": self.lipsync_nim_tags_selector,
            "s2s_default_target_language": self.s2s_default_target_language,
            "default_source_language": self.default_source_language,
            "default_target_language": self.default_target_language,
            "lipsync_nvidia_function_id": self.lipsync_nvidia_function_id,
            "asd_nvidia_function_id": self.asd_nvidia_function_id,
            "nvidia_serverless_grpc_host": self.nvidia_serverless_grpc_host,
            "nvidia_serverless_grpc_port": self.nvidia_serverless_grpc_port,
            "reference_app_enable_preprocessing": self.reference_app_enable_preprocessing,
            "voice_name": self.voice_name,
            "target_language_label": self.target_language_label,
        }

    @classmethod
    def merge_update(cls, existing: AppConfig | None, patch: dict[str, Any]) -> AppConfig:
        """Merge Setup page form data; blank secret fields keep existing values."""
        merged = existing.to_dict() if existing else {}
        for key, value in patch.items():
            if key in SECRET_KEYS and not str(value or "").strip():
                continue
            merged[key] = value
        return cls.from_dict(merged)

    def secrets_set(self) -> dict[str, bool]:
        return {
            "ngc_api_key": bool(self.ngc_api_key),
            "elevenlabs_api_key": bool(self.elevenlabs_api_key),
            "camb_api_key": bool(self.camb_api_key),
        }

    def public_dict(self) -> dict[str, Any]:
        """Non-secret fields for repopulating the Setup form."""
        data = self.to_dict()
        for key in SECRET_KEYS:
            data.pop(key, None)
        return data

    def masked_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        for key in SECRET_KEYS:
            data[key] = "********" if data.get(key) else ""
        return data

    def as_process_env(self) -> dict[str, str]:
        raw = self.to_dict()
        raw["reference_app_enable_preprocessing"] = (
            "true" if self.reference_app_enable_preprocessing else "false"
        )
        env: dict[str, str] = {}
        for json_key, env_key in _ENV_MAP.items():
            value = raw.get(json_key)
            if value is None or value == "":
                continue
            env[env_key] = str(value)
        # Keep demo + S2S defaults aligned
        env.setdefault("DEFAULT_TARGET_LANGUAGE", self.default_target_language)
        env.setdefault("S2S_DEFAULT_TARGET_LANGUAGE", self.s2s_default_target_language)
        return env

    def apply_to_environ(self) -> dict[str, str]:
        env = self.as_process_env()
        os.environ.update(env)
        return env

    def app_environment(self) -> dict[str, str]:
        env = self.as_process_env()
        env["TASK_TYPE"] = "START_APPLICATION"
        return env

    def validate_for_build(self) -> dict[str, Any]:
        """Return {valid, errors, warnings} before starting a pipeline build."""
        errors: list[str] = []
        warnings: list[str] = []

        mode = self.nim_deploy_mode.upper()
        if mode not in {"SERVERLESS", "BUNDLED"}:
            errors.append(f"Invalid NIM deployment mode: {self.nim_deploy_mode}")

        if not self.ngc_api_key.strip():
            errors.append("NGC API key is required.")

        if self.s2s_service == "EL_DUBBING":
            if not self.elevenlabs_api_key.strip():
                errors.append("ElevenLabs API key is required for ElevenLabs dubbing.")
        elif self.s2s_service == "CAMB_DUBBING":
            if not self.camb_api_key.strip():
                errors.append("CambAI API key is required for CambAI dubbing.")
        else:
            errors.append(f"Unsupported S2S backend: {self.s2s_service}")

        if not self.default_target_language.strip():
            errors.append("Default target language is required.")
        if not self.default_source_language.strip():
            errors.append("Default source language is required.")

        if mode == "BUNDLED" and not self.lipsync_nim_tags_selector.strip():
            errors.append("LipSync language model (NIM_TAGS_SELECTOR) is required for bundled mode.")

        port = self.nvidia_serverless_grpc_port.strip()
        if port and not port.isdigit():
            errors.append("NVCF gRPC port must be a number.")

        if self.reference_app_enable_preprocessing and self.s2s_service == "EL_DUBBING":
            if not self.elevenlabs_api_key.strip():
                errors.append("ElevenLabs API key is required when preprocessing is enabled.")

        if mode == "SERVERLESS":
            warnings.append(
                "Serverless mode uses NVIDIA NVCF for LipSync and ASD — no GPU NIM apps are created in this project."
            )
        else:
            warnings.append(
                "Bundled mode starts GPU NIM applications; LipSync and ASD can take 15–30+ minutes to become ready."
            )

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def validate_merged_config(patch: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate saved config, optionally merged with unsaved form fields."""
    existing = load_app_config()
    config = AppConfig.merge_update(existing, patch or {}) if patch else existing
    if config is None:
        return {"valid": False, "errors": ["Save your configuration before building."], "warnings": []}
    return config.validate_for_build()


def load_app_config() -> AppConfig | None:
    if not DEPLOYMENT_CONFIG_JSON.exists():
        return None
    raw = DEPLOYMENT_CONFIG_JSON.read_text().strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return AppConfig.from_dict(data)


def deployment_config_load_error() -> str | None:
    """Human-readable reason saved config cannot be loaded, if the file exists."""
    if not DEPLOYMENT_CONFIG_JSON.exists():
        return None
    raw = DEPLOYMENT_CONFIG_JSON.read_text().strip()
    if not raw:
        return (
            f"{DEPLOYMENT_CONFIG_JSON.name} is empty — click Save configuration, "
            "then redeploy the pipeline."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return (
            f"{DEPLOYMENT_CONFIG_JSON.name} is invalid JSON ({exc.msg}) — "
            "click Save configuration, then redeploy the pipeline."
        )
    if not isinstance(data, dict):
        return (
            f"{DEPLOYMENT_CONFIG_JSON.name} must be a JSON object — "
            "click Save configuration, then redeploy the pipeline."
        )
    return None


def save_app_config(config: AppConfig) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(config.to_dict(), indent=2) + "\n"
    tmp_path = DEPLOYMENT_CONFIG_JSON.with_suffix(".json.tmp")
    tmp_path.write_text(payload)
    tmp_path.replace(DEPLOYMENT_CONFIG_JSON)
    env = config.apply_to_environ()
    write_dotenv_file(APP_ENVIRONMENT_ENV, env)
    return DEPLOYMENT_CONFIG_JSON


def apply_persisted_config() -> AppConfig | None:
    """Load persisted Setup configuration into os.environ (call on every app start)."""
    config = load_app_config()
    if config is None:
        return None
    config.apply_to_environ()
    return config


# Backward-compatible aliases used by deployment_control
DeploymentConfig = AppConfig
load_deployment_config = load_app_config
save_deployment_config = save_app_config
