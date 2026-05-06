import getpass
import os

import keyring
from keyring.errors import KeyringError


_PROVIDER_KEY_ENVS: tuple[str, ...] = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
_KEYRING_SERVICE = "glyph-agents"
_BOOTSTRAP_DONE = False

_AUTH_PROMPTS: dict[str, str] = {
    "OPENAI_API_KEY": "OpenAI API key (leave empty to skip): ",
    "ANTHROPIC_API_KEY": "Anthropic API key (leave empty to skip): ",
}


def _load_keyring_into_env(env_name: str) -> None:
    try:
        stored = keyring.get_password(_KEYRING_SERVICE, env_name)
    except Exception:
        return
    if not stored:
        return
    os.environ[env_name] = stored


def store_provider_keyring_credential(env_name: str, value: str) -> None:
    """Persist a provider API key to the user keyring (non-empty ``value`` only)."""
    stripped = value.strip()
    if not stripped:
        return

    try:
        keyring.set_password(_KEYRING_SERVICE, env_name, stripped)
    except KeyringError as exc:
        print(
            f"Unable to store {env_name} in the system keyring: {exc}. "
            "Check that a keyring backend is available and unlocked."
        )



def interactive_configure_provider_keys() -> None:
    """Prompt for OPENAI_API_KEY and ANTHROPIC_API_KEY; blank input skips that key."""
    for env_name in _PROVIDER_KEY_ENVS:
        prompt = _AUTH_PROMPTS.get(env_name, f"{env_name} (leave empty to skip): ")
        secret = getpass.getpass(prompt)
        if not secret.strip():
            continue
        store_provider_keyring_credential(env_name, secret)


def bootstrap_provider_api_keys() -> None:
    """Wire OPENAI_API_KEY / ANTHROPIC_API_KEY from the user keyring when needed.

    - When a non-empty value is already in the environment, it is left unchanged
      and the keyring is not updated (use ``glyph auth`` to store secrets).
    - When a variable is absent from the environment, or present but blank, and
      the keyring holds a value, expose it via ``os.environ`` so vendor SDKs
      keep working.
    - When neither side has a value, do nothing (connection may fail later).
    """
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return
    _BOOTSTRAP_DONE = True

    for env_name in _PROVIDER_KEY_ENVS:
        if env_name in os.environ and os.environ[env_name].strip() != "":
            continue
        _load_keyring_into_env(env_name)

