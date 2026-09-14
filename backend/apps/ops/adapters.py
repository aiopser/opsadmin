"""Execution-time credential port for the ops executor core.

Ops consumes execution plans only: it never reads CMDB models directly.
Concrete providers (e.g. the CMDB-backed one) live in their owning apps and
are injected at plan-building time.
"""

from typing import Any, Mapping


class CredentialProvider:
    def resolve(self, credential_id: int) -> Mapping[str, Any]:
        raise NotImplementedError
