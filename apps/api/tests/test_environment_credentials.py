import runpy
from pathlib import Path

import pytest
from evaldock.config import Settings, settings
from evaldock.db import uid
from evaldock.models import Credential
from evaldock.security import credential_secret, credential_source, encrypt
from pydantic import SecretStr


def test_environment_key_is_explicitly_scoped_and_never_falls_back(monkeypatch):
    bound = Credential(
        id=uid(), project_id=uid(), name="OpenAI", ciphertext=encrypt("old-database-key")
    )
    other = Credential(
        id=uid(), project_id=uid(), name="OpenAI", ciphertext=encrypt("other-project-key")
    )
    monkeypatch.setattr(settings(), "openai_credential_id", bound.id)
    monkeypatch.setattr(settings(), "openai_api_key", SecretStr("server-test-key"))
    assert credential_source(bound) == "environment"
    assert credential_secret(bound) == "server-test-key"
    assert credential_source(other) == "database"
    assert credential_secret(other) == "other-project-key"
    monkeypatch.setattr(settings(), "openai_api_key", SecretStr(""))
    assert credential_secret(bound) == ""
    config = Settings(_env_file=None, openai_api_key="server-test-key")
    assert "server-test-key" not in repr(config)
    assert "server-test-key" not in config.model_dump_json()


def test_environment_binding_preserves_existing_keys_and_is_idempotent(tmp_path):
    script = Path(__file__).resolve().parents[3] / "scripts/configure_catalog_ai.py"
    bind = runpy.run_path(str(script))["bind_environment"]
    path = tmp_path / ".env"
    original = "# Local configuration\nAPP_KEY=test-existing-encryption-key\nOPENAI_API_KEY='test-existing-provider-key'\nOPENAI_CREDENTIAL_ID=\n"
    path.write_text(original)
    bind(path, "test-credential-id")
    content = path.read_text()
    assert content == original.replace(
        "OPENAI_CREDENTIAL_ID=\n", "OPENAI_CREDENTIAL_ID=test-credential-id\n"
    )
    assert path.stat().st_mode & 0o777 == 0o600
    bind(path, "test-credential-id")
    assert path.read_text() == content
    with pytest.raises(ValueError, match="another credential"):
        bind(path, "other-id")
    assert path.read_text() == content


def test_environment_binding_creates_an_empty_key_slot(tmp_path):
    script = Path(__file__).resolve().parents[3] / "scripts/configure_catalog_ai.py"
    bind = runpy.run_path(str(script))["bind_environment"]
    path = tmp_path / ".env"
    path.write_text("APP_KEY=test-existing-key\n")
    bind(path, "test-slot")
    assert "APP_KEY=test-existing-key\n" in path.read_text()
    assert "OPENAI_API_KEY=\n" in path.read_text()
    assert "OPENAI_CREDENTIAL_ID=test-slot\n" in path.read_text()
