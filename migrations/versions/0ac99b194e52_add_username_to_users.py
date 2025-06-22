"""add username to users

Revision ID: 0ac99b194e52
Revises: 31f86e39c9a3
Create Date: 2025-06-22 02:42:05.123456

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0ac99b194e52'
down_revision = '31f86e39c9a3'
branch_labels = None
depends_on = None

def upgrade():
    # Add the username column with a default value (e.g., empty string) to avoid NULLs
    op.add_column('users', sa.Column('username', sa.String(length=80), nullable=True))
    
    # Update existing rows to set username to email as a fallback
    op.execute("UPDATE users SET username = email WHERE username IS NULL")
    
    # Alter the column to make it NOT NULL and add the unique constraint
    op.alter_column('users', 'username', nullable=False)
    op.create_unique_constraint(None, 'users', ['username'])

def downgrade():
    # Remove the unique constraint and drop the column
    op.drop_constraint('users_username_key', 'users', type_='unique')
    op.drop_column('users', 'username')