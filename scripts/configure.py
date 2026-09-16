"""Generate secrets locally without printing them or modifying existing configuration."""

import base64
import os
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".env"
if path.exists():
    print("Existing .env retained")
else:
    password = secrets.token_urlsafe(24)
    demo = secrets.token_urlsafe(18)
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    content = f"DATABASE_URL=postgresql+psycopg://evaldock:{password}@localhost:5492/evaldock\nPOSTGRES_PASSWORD={password}\nAPP_KEY={key}\nPUBLIC_ORIGIN=http://localhost:5188\nCOOKIE_SECURE=false\nALLOWED_TARGET_ORIGINS=http://samples:8090,http://localhost:8099\nSAMPLE_ORIGIN=http://samples:8090\nDEMO_PASSWORD={demo}\nARTIFACT_DIR=artifacts\n\n# Shared by the prepared OpenAI target and judge.\nOPENAI_API_KEY=\n# Managed by scripts/configure_catalog_ai.py.\nOPENAI_CREDENTIAL_ID=\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(content)
    print("Created .env with random local secrets (mode 0600)")
