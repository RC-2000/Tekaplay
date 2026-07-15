"""Identity core: users, organizations, RBAC, audit, auth tokens.

Also seeds code-defined permissions and the three system roles. Permission
codes are owned by code (this migration + future ones); role↔permission
composition beyond the seed is runtime data managed in the admin panel.

Revision ID: 0001
Revises:
Create Date: 2026-07-15
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("theme", sa.String(16), nullable=False, server_default="system"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        _uuid_pk(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "organization_members",
        _uuid_pk(),
        sa.Column("organization_id", sa.Uuid(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
    )
    op.create_index("ix_organization_members_organization_id",
                    "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id",
                    "organization_members", ["user_id"])

    op.create_table(
        "permissions",
        _uuid_pk(),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"], unique=True)

    op.create_table(
        "roles",
        _uuid_pk(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "role_permissions",
        _uuid_pk(),
        sa.Column("role_id", sa.Uuid(),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Uuid(),
                  sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_id", "role_permissions", ["permission_id"])

    op.create_table(
        "user_roles",
        _uuid_pk(),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Uuid(),
                  sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.Uuid(),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_role_scope"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    op.create_table(
        "audit_logs",
        _uuid_pk(),
        sa.Column("actor_user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(120)),
        sa.Column("entity_id", sa.Uuid()),
        sa.Column("meta", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(64)),
        *_timestamps(),
    )
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "refresh_tokens",
        _uuid_pk(),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(400)),
        *_timestamps(),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    op.create_table(
        "oauth_accounts",
        _uuid_pk(),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        *_timestamps(),
        sa.UniqueConstraint("provider", "provider_account_id",
                            name="uq_oauth_provider_account"),
    )
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])

    op.create_table(
        "action_tokens",
        _uuid_pk(),
        sa.Column("user_id", sa.Uuid(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        *_timestamps(),
    )
    op.create_index("ix_action_tokens_token_hash", "action_tokens", ["token_hash"], unique=True)
    op.create_index("ix_action_tokens_user_id", "action_tokens", ["user_id"])

    _seed_rbac()


_PERMISSIONS = {
    "admin.access": "Access the admin panel",
    "users.read": "List and view users",
    "users.manage": "Create, modify, and deactivate users",
    "roles.manage": "Manage roles and permission assignments",
    "orgs.manage": "Manage organizations and memberships",
    "content.read": "View published learning content",
    "content.author": "Create and edit draft content in Creator Studio",
    "content.publish": "Publish and roll back content versions",
    "audit.read": "View audit logs",
}

_ROLES = {
    "admin": ("Full platform administration", list(_PERMISSIONS)),
    "creator": ("Builds and publishes content",
                ["content.read", "content.author", "content.publish"]),
    "learner": ("Standard player account", ["content.read"]),
}


def _seed_rbac() -> None:
    bind = op.get_bind()
    perm_ids: dict[str, uuid.UUID] = {}
    for code, description in _PERMISSIONS.items():
        pid = uuid.uuid4()
        perm_ids[code] = pid
        bind.execute(
            sa.text("INSERT INTO permissions (id, code, description) "
                    "VALUES (:id, :code, :description)"),
            {"id": pid, "code": code, "description": description},
        )
    for name, (description, codes) in _ROLES.items():
        rid = uuid.uuid4()
        bind.execute(
            sa.text("INSERT INTO roles (id, name, description, is_system) "
                    "VALUES (:id, :name, :description, true)"),
            {"id": rid, "name": name, "description": description},
        )
        for code in codes:
            bind.execute(
                sa.text("INSERT INTO role_permissions (id, role_id, permission_id) "
                        "VALUES (:id, :role_id, :permission_id)"),
                {"id": uuid.uuid4(), "role_id": rid, "permission_id": perm_ids[code]},
            )


def downgrade() -> None:
    for table in ("action_tokens", "oauth_accounts", "refresh_tokens", "audit_logs",
                  "user_roles", "role_permissions", "roles", "permissions",
                  "organization_members", "organizations", "users"):
        op.drop_table(table)
