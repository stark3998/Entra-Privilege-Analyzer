# backend/app/services/iac_exporter.py
"""Generates IaC (Terraform, Bicep, ARM) from role recommendations."""
from __future__ import annotations

import json
import logging
import re
import textwrap

from app.models.export import ExportFormat, ExportResult
from app.models.role import RoleRecommendation, RoleScope

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r"^[a-zA-Z0-9./*_\- ]+$")


def _sanitize_hcl(value: str) -> str:
    """Escape characters special in HCL double-quoted strings."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _sanitize_bicep(value: str) -> str:
    """Escape characters special in Bicep single-quoted strings."""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


class IacExporter:
    """Exports a ``RoleRecommendation``'s custom role to IaC code."""

    def export(self, rec: RoleRecommendation, fmt: ExportFormat) -> ExportResult:
        """Dispatch to the appropriate format exporter."""
        if fmt == ExportFormat.TERRAFORM:
            return self.export_terraform(rec)
        if fmt == ExportFormat.BICEP:
            return self.export_bicep(rec)
        return self.export_arm(rec)

    # ------------------------------------------------------------------
    # Terraform
    # ------------------------------------------------------------------

    def export_terraform(self, rec: RoleRecommendation) -> ExportResult:
        """Generate Terraform HCL for the custom role."""
        cr = rec.custom_role
        safe_name = cr.name.lower().replace("-", "_")

        if cr.scope == RoleScope.ENTRA:
            content = self._terraform_entra(cr.name, cr.description, cr.permissions, safe_name)
        else:
            content = self._terraform_azure(
                cr.name, cr.description, cr.permissions, cr.is_assignable_scopes, safe_name,
            )

        return ExportResult(
            format=ExportFormat.TERRAFORM,
            identity_id=rec.identity_id,
            content=content,
            filename=f"{safe_name}.tf",
        )

    @staticmethod
    def _terraform_entra(
        name: str, description: str, permissions: list[str], safe_name: str,
    ) -> str:
        perm_lines = "\n".join(f'      "{_sanitize_hcl(p)}",' for p in permissions)
        return textwrap.dedent(f"""\
            resource "azuread_custom_directory_role" "{_sanitize_hcl(safe_name)}" {{
              display_name = "{_sanitize_hcl(name)}"
              description  = "{_sanitize_hcl(description)}"
              enabled      = true

              permissions {{
                allowed_resource_actions = [
            {perm_lines}
                ]
              }}
            }}
        """)

    @staticmethod
    def _terraform_azure(
        name: str,
        description: str,
        permissions: list[str],
        assignable_scopes: list[str],
        safe_name: str,
    ) -> str:
        action_lines = "\n".join(f'      "{_sanitize_hcl(p)}",' for p in permissions)
        scope_lines = "\n".join(f'    "{_sanitize_hcl(s)}",' for s in assignable_scopes)
        first_scope = _sanitize_hcl(assignable_scopes[0]) if assignable_scopes else "/"
        return textwrap.dedent(f"""\
            resource "azurerm_role_definition" "{_sanitize_hcl(safe_name)}" {{
              name        = "{_sanitize_hcl(name)}"
              description = "{_sanitize_hcl(description)}"
              scope       = "{first_scope}"

              permissions {{
                actions = [
            {action_lines}
                ]
              }}

              assignable_scopes = [
            {scope_lines}
              ]
            }}
        """)

    # ------------------------------------------------------------------
    # Bicep
    # ------------------------------------------------------------------

    def export_bicep(self, rec: RoleRecommendation) -> ExportResult:
        """Generate Bicep resource definition for the custom role."""
        cr = rec.custom_role
        safe_name = cr.name.lower().replace("-", "_")

        if cr.scope == RoleScope.ENTRA:
            content = self._bicep_entra(cr.name, cr.description, cr.permissions)
        else:
            content = self._bicep_azure(
                cr.name, cr.description, cr.permissions, cr.is_assignable_scopes,
            )

        return ExportResult(
            format=ExportFormat.BICEP,
            identity_id=rec.identity_id,
            content=content,
            filename=f"{safe_name}.bicep",
        )

    @staticmethod
    def _bicep_entra(name: str, description: str, permissions: list[str]) -> str:
        perm_lines = "\n".join(f"        '{_sanitize_bicep(p)}'" for p in permissions)
        return textwrap.dedent(f"""\
            resource customRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {{
              name: guid('{_sanitize_bicep(name)}')
              properties: {{
                roleName: '{_sanitize_bicep(name)}'
                description: '{_sanitize_bicep(description)}'
                type: 'CustomRole'
                permissions: [
                  {{
                    actions: [
            {perm_lines}
                    ]
                  }}
                ]
                assignableScopes: [
                  subscription().id
                ]
              }}
            }}
        """)

    @staticmethod
    def _bicep_azure(
        name: str, description: str, permissions: list[str], scopes: list[str],
    ) -> str:
        action_lines = "\n".join(f"        '{_sanitize_bicep(p)}'" for p in permissions)
        scope_lines = "\n".join(f"    '{_sanitize_bicep(s)}'" for s in scopes)
        return textwrap.dedent(f"""\
            resource customRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {{
              name: guid('{_sanitize_bicep(name)}')
              properties: {{
                roleName: '{_sanitize_bicep(name)}'
                description: '{_sanitize_bicep(description)}'
                type: 'CustomRole'
                permissions: [
                  {{
                    actions: [
            {action_lines}
                    ]
                  }}
                ]
                assignableScopes: [
            {scope_lines}
                ]
              }}
            }}
        """)

    # ------------------------------------------------------------------
    # ARM JSON
    # ------------------------------------------------------------------

    def export_arm(self, rec: RoleRecommendation) -> ExportResult:
        """Generate ARM JSON template for the custom role."""
        cr = rec.custom_role
        safe_name = cr.name.lower().replace("-", "_")

        template: dict[str, object] = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [
                {
                    "type": "Microsoft.Authorization/roleDefinitions",
                    "apiVersion": "2022-04-01",
                    "name": f"[guid('{cr.name}')]",
                    "properties": {
                        "roleName": cr.name,
                        "description": cr.description,
                        "type": "CustomRole",
                        "permissions": [
                            {
                                "actions": cr.permissions,
                                "notActions": [],
                                "dataActions": [],
                                "notDataActions": [],
                            }
                        ],
                        "assignableScopes": cr.is_assignable_scopes,
                    },
                }
            ],
        }

        content = json.dumps(template, indent=2)

        return ExportResult(
            format=ExportFormat.ARM,
            identity_id=rec.identity_id,
            content=content,
            filename=f"{safe_name}.json",
        )
