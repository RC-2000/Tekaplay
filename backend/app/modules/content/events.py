"""Lifecycle events. content.published itself is emitted by the runtime when
the live definition row is created — single source of truth."""
DRAFT_CREATED = "content.draft_created"
SUBMITTED = "content.submitted"
APPROVED = "content.approved"
REJECTED = "content.rejected"
ROLLED_BACK = "content.rolled_back"
