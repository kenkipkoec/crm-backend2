"""add book_id and accounting book logic

Revision ID: 5e9ed84c7a97
Revises: 
Create Date: 2025-06-10 10:11:11.778552

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e9ed84c7a97'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add book_id as nullable to account and journal_entry
    op.add_column('account', sa.Column('book_id', sa.Integer(), nullable=True))
    op.add_column('journal_entry', sa.Column('book_id', sa.Integer(), nullable=True))

    # 2. Create accounting_book table if not already created by this migration
    # (If this migration already creates the table, skip this step)
    op.create_table('accounting_book',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_unique_constraint(
        "uq_accounting_book_user_id_name",
        "accounting_book",
        ["user_id", "name"]
    )

    # 3. Data migration: For each user, create a default book and assign book_id to all their accounts and journal entries
    conn = op.get_bind()
    # Create a default book for each user who has accounts
    conn.execute(sa.text("""
        INSERT INTO accounting_book (user_id, name, created_at)
        SELECT DISTINCT user_id, 'Default Book', NOW()
        FROM account
        WHERE user_id IS NOT NULL
        ON CONFLICT (user_id, name) DO NOTHING
    """))
    # Assign book_id to accounts
    conn.execute(sa.text("""
        UPDATE account
        SET book_id = ab.id
        FROM accounting_book ab
        WHERE account.user_id = ab.user_id AND ab.name = 'Default Book'
    """))
    # Assign book_id to journal entries
    conn.execute(sa.text("""
        UPDATE journal_entry
        SET book_id = ab.id
        FROM accounting_book ab
        WHERE journal_entry.user_id = ab.user_id AND ab.name = 'Default Book'
    """))

    # 4. Alter book_id columns to NOT NULL
    op.alter_column('account', 'book_id', nullable=False)
    op.alter_column('journal_entry', 'book_id', nullable=False)

    # 5. Add foreign key constraints
    op.create_foreign_key('fk_account_book_id', 'account', 'accounting_book', ['book_id'], ['id'])
    op.create_foreign_key('fk_journal_entry_book_id', 'journal_entry', 'accounting_book', ['book_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('journal_entry', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('book_id')
        batch_op.drop_column('status')
        batch_op.drop_column('attachment')

    with op.batch_alter_table('account', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('book_id')
        batch_op.drop_column('parent_id')
        batch_op.drop_column('category')

    op.drop_table('accounting_book')
    # ### end Alembic commands ###
