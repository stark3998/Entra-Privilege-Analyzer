from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.governance import (
    AuthorizationConfiguration,
    AuthorizationMode,
    AuthorizationReadiness,
)

_READ_PERMISSIONS = {
    "AuditLog.Read.All",
    "Directory.Read.All",
    "RoleManagement.Read.Directory",
}
_WRITE_PERMISSIONS = {
    "RoleManagement.ReadWrite.Directory",
    "PrivilegedAccess.ReadWrite.AzureAD",
}


class AuthorizationReadinessService:
    def evaluate(
        self,
        configuration: AuthorizationConfiguration,
    ) -> AuthorizationReadiness:
        missing: list[str] = []
        warnings: list[str] = []
        collection_ready = False
        mutation_ready = False
        delegated_ready = False
        if configuration.mode == AuthorizationMode.SPLIT_APPLICATIONS:
            collection_ready = bool(
                configuration.collection_client_id
                and configuration.collection_credential_reference
                and _READ_PERMISSIONS.issubset(configuration.collection_permissions)
            )
            mutation_ready = bool(
                configuration.mutation_client_id
                and configuration.mutation_credential_reference
                and _WRITE_PERMISSIONS.issubset(configuration.mutation_permissions)
            )
            if configuration.collection_client_id == configuration.mutation_client_id:
                missing.append("Split mode requires distinct collection and mutation apps")
        elif configuration.mode == AuthorizationMode.COMBINED_APPLICATION:
            collection_ready = mutation_ready = bool(
                configuration.collection_client_id
                and configuration.collection_credential_reference
                and (_READ_PERMISSIONS | _WRITE_PERMISSIONS).issubset(
                    set(configuration.collection_permissions)
                    | set(configuration.mutation_permissions)
                )
            )
            warnings.append("Combined mode increases credential blast radius")
        else:
            delegated_ready = bool(configuration.delegated_scopes)
            collection_ready = delegated_ready
            mutation_ready = delegated_ready
            if not delegated_ready:
                missing.append("Delegated OBO scopes are not configured")

        now = datetime.now(UTC)
        if (
            configuration.credential_expires_at
            and configuration.credential_expires_at <= now + timedelta(days=30)
        ):
            warnings.append("Credential expires within 30 days")
        if not collection_ready:
            missing.append("Collection permissions or credential reference are incomplete")
        if not mutation_ready:
            missing.append("Mutation permissions or credential reference are incomplete")
        return AuthorizationReadiness(
            mode=configuration.mode,
            ready=collection_ready and mutation_ready and not missing,
            collection_ready=collection_ready,
            mutation_ready=mutation_ready,
            delegated_ready=delegated_ready,
            missing=sorted(set(missing)),
            warnings=warnings,
            checked_at=now,
        )
