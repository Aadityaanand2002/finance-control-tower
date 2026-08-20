"""Initial schema — application also uses Base.metadata.create_all on startup."""

from typing import Sequence, Union

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are created via SQLAlchemy metadata in app startup / seed.
    pass


def downgrade() -> None:
    pass
