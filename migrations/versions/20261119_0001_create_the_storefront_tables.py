"""create the storefront tables

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('products',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('sku', sa.String(length=120), nullable=False),
    sa.Column('pid', sa.String(length=120), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('size', sa.String(length=60), nullable=True),
    sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('was', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('category', sa.String(length=60), nullable=False),
    sa.Column('blurb', sa.Text(), server_default='', nullable=False),
    sa.Column('stock', sa.Integer(), server_default='0', nullable=False),
    sa.Column('channel', sa.String(length=10), server_default='retail', nullable=False),
    sa.Column('image', sa.String(length=500), nullable=True),
    sa.Column('country', sa.String(length=60), nullable=True),
    sa.Column('business_group', sa.String(length=80), nullable=True),
    sa.Column('brand', sa.String(length=80), nullable=True),
    sa.Column('sub_brand', sa.String(length=80), nullable=True),
    sa.Column('segment', sa.String(length=80), nullable=True),
    sa.Column('form', sa.String(length=40), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("channel IN ('retail', 'bulk')", name=op.f('ck_products_channel_valid')),
    sa.CheckConstraint('price >= 0', name=op.f('ck_products_price_not_negative')),
    sa.CheckConstraint('stock >= 0', name=op.f('ck_products_stock_not_negative')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_products'))
    )
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)
    op.create_index(op.f('ix_products_deleted_at'), 'products', ['deleted_at'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('employee_id', sa.String(length=40), nullable=True),
    sa.Column('password_hash', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    # emails, employee IDs and SKUs are unique regardless of capitals (Alembic cannot autogenerate expression indexes)
    op.create_index('uq_users_email_lower', 'users', [sa.text('lower(email)')], unique=True)
    op.create_index('uq_users_employee_id_lower', 'users', [sa.text('lower(employee_id)')], unique=True)
    op.create_index('uq_products_sku_lower', 'products', [sa.text('lower(sku)')], unique=True)

    op.create_table('import_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=True),
    sa.Column('total_rows', sa.Integer(), nullable=False),
    sa.Column('added', sa.Integer(), nullable=False),
    sa.Column('updated', sa.Integer(), nullable=False),
    sa.Column('skipped', sa.Integer(), nullable=False),
    sa.Column('issues', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_import_jobs_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_jobs'))
    )
    op.create_index(op.f('ix_import_jobs_user_id'), 'import_jobs', ['user_id'], unique=False)

    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ref', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('card_last4', sa.String(length=4), nullable=True),
    sa.Column('failure_reason', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_payments_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
    sa.UniqueConstraint('ref', name=op.f('uq_payments_ref'))
    )
    op.create_index(op.f('ix_payments_user_id'), 'payments', ['user_id'], unique=False)

    op.create_table('stock_locations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=64), nullable=False),
    sa.Column('system_id', sa.String(length=40), nullable=False),
    sa.Column('location_id', sa.String(length=60), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('uom', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.CheckConstraint('quantity >= 0', name=op.f('ck_stock_locations_quantity_not_negative')),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_stock_locations_product_id_products'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_locations')),
    sa.UniqueConstraint('product_id', 'system_id', 'location_id', name='uq_stock_locations_place')
    )
    op.create_index(op.f('ix_stock_locations_product_id'), 'stock_locations', ['product_id'], unique=False)

    op.create_table('orders',
    sa.Column('id', sa.Integer(), sa.Identity(always=False, start=1001), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('payment_id', sa.Integer(), nullable=True),
    sa.Column('channel', sa.String(length=10), nullable=False),
    sa.Column('step', sa.Integer(), server_default='0', nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('customer_name', sa.String(length=120), nullable=False),
    sa.Column('customer_email', sa.String(length=254), nullable=False),
    sa.Column('ship_full_name', sa.String(length=120), nullable=False),
    sa.Column('ship_phone', sa.String(length=30), nullable=False),
    sa.Column('ship_line1', sa.String(length=200), nullable=False),
    sa.Column('ship_line2', sa.String(length=200), server_default='', nullable=False),
    sa.Column('ship_city', sa.String(length=80), nullable=False),
    sa.Column('ship_state', sa.String(length=80), nullable=False),
    sa.Column('ship_pin', sa.String(length=10), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("channel IN ('retail', 'bulk')", name=op.f('ck_orders_channel_valid')),
    sa.CheckConstraint('step BETWEEN 0 AND 3', name=op.f('ck_orders_step_valid')),
    sa.CheckConstraint('total >= 0', name=op.f('ck_orders_total_not_negative')),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], name=op.f('fk_orders_payment_id_payments')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_orders_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_orders'))
    )
    op.create_index(op.f('ix_orders_created_at'), 'orders', ['created_at'], unique=False)
    op.create_index(op.f('ix_orders_deleted_at'), 'orders', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_orders_payment_id'), 'orders', ['payment_id'], unique=False)
    op.create_index(op.f('ix_orders_ship_city'), 'orders', ['ship_city'], unique=False)
    op.create_index(op.f('ix_orders_ship_state'), 'orders', ['ship_state'], unique=False)
    op.create_index(op.f('ix_orders_user_id'), 'orders', ['user_id'], unique=False)

    op.create_table('order_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('size', sa.String(length=60), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('qty', sa.Integer(), nullable=False),
    sa.CheckConstraint('qty >= 1', name=op.f('ck_order_items_qty_positive')),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_items_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_order_items_product_id_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_items'))
    )
    op.create_index(op.f('ix_order_items_order_id'), 'order_items', ['order_id'], unique=False)
    op.create_index(op.f('ix_order_items_product_id'), 'order_items', ['product_id'], unique=False)



def downgrade() -> None:
    op.drop_index(op.f('ix_order_items_product_id'), table_name='order_items')
    op.drop_index(op.f('ix_order_items_order_id'), table_name='order_items')

    op.drop_table('order_items')
    op.drop_index(op.f('ix_orders_user_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_ship_state'), table_name='orders')
    op.drop_index(op.f('ix_orders_ship_city'), table_name='orders')
    op.drop_index(op.f('ix_orders_payment_id'), table_name='orders')
    op.drop_index(op.f('ix_orders_deleted_at'), table_name='orders')
    op.drop_index(op.f('ix_orders_created_at'), table_name='orders')

    op.drop_table('orders')
    op.drop_index(op.f('ix_stock_locations_product_id'), table_name='stock_locations')

    op.drop_table('stock_locations')
    op.drop_index(op.f('ix_payments_user_id'), table_name='payments')

    op.drop_table('payments')
    op.drop_index(op.f('ix_import_jobs_user_id'), table_name='import_jobs')

    op.drop_table('import_jobs')
    op.drop_index('uq_users_employee_id_lower', table_name='users')
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_products_deleted_at'), table_name='products')
    op.drop_index(op.f('ix_products_category'), table_name='products')

    op.drop_index('uq_products_sku_lower', table_name='products')
    op.drop_table('products')
