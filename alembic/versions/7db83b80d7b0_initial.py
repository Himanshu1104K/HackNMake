"""initial

Revision ID: 7db83b80d7b0
Revises:
Create Date: 2026-01-10 17:51:03.257680

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7db83b80d7b0"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create function to update updated_at timestamp
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """
    )

    # Create function to generate random health values (best to worst efficiency)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION generate_random_health_values()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Generate random blood_pressure (normal: 90-120/60-80 to high: 140-180/90-120)
            IF NEW.blood_pressure IS NULL THEN
                NEW.blood_pressure := jsonb_build_object(
                    'systolic', floor(random() * (180 - 90 + 1) + 90)::integer,
                    'diastolic', floor(random() * (120 - 60 + 1) + 60)::integer
                );
            END IF;
            
            -- Generate random body_temp (normal: 36.5-37.5°C to fever: 38.0-40.0°C)
            IF NEW.body_temp IS NULL THEN
                NEW.body_temp := round((random() * (40.0 - 36.5) + 36.5)::numeric, 1);
            END IF;
            
            -- Generate random heart_rate (normal: 60-100 bpm to high: 100-150 bpm)
            IF NEW.heart_rate IS NULL THEN
                NEW.heart_rate := floor(random() * (150 - 60 + 1) + 60)::integer;
            END IF;
            
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """
    )

    # Create animals table
    op.create_table(
        "animals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create trigger for animals table
    op.execute("DROP TRIGGER IF EXISTS update_animals_updated_at ON animals")
    op.execute(
        """
        CREATE TRIGGER update_animals_updated_at
        BEFORE UPDATE ON animals
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    )

    # Create animal table
    op.create_table(
        "animal",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("animal_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["animal_id"], ["animals.id"], name="fk_animal_animals"
        ),
    )

    # Create indexes for animal table
    op.execute("CREATE INDEX IF NOT EXISTS idx_animal_animal_id ON animal(animal_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_animal_status ON animal(status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_animal_is_critical ON animal(is_critical)"
    )

    # Create trigger for animal table
    op.execute("DROP TRIGGER IF EXISTS update_animal_updated_at ON animal")
    op.execute(
        """
        CREATE TRIGGER update_animal_updated_at
        BEFORE UPDATE ON animal
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    )

    # Create data table
    op.create_table(
        "data",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("animal_id", sa.String(), nullable=False),
        sa.Column("accelerometer", sa.String(), nullable=True),
        sa.Column("gyroscrope", sa.String(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column(
            "blood_pressure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("body_temp", sa.Float(), nullable=True),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["animal_id"], ["animal.id"], name="fk_data_animal"),
    )

    # Create indexes for data table
    op.execute("CREATE INDEX IF NOT EXISTS idx_data_animal_id ON data(animal_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_data_created_at ON data(created_at)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_data_location ON data(latitude, longitude)"
    )

    # Create triggers for data table
    op.execute("DROP TRIGGER IF EXISTS update_data_updated_at ON data")
    op.execute(
        """
        CREATE TRIGGER update_data_updated_at
        BEFORE UPDATE ON data
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    )

    op.execute("DROP TRIGGER IF EXISTS generate_data_health_values ON data")
    op.execute(
        """
        CREATE TRIGGER generate_data_health_values
        BEFORE INSERT ON data
        FOR EACH ROW
        EXECUTE FUNCTION generate_random_health_values();
    """
    )


def downgrade() -> None:
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_data_location")
    op.execute("DROP INDEX IF EXISTS idx_data_created_at")
    op.execute("DROP INDEX IF EXISTS idx_data_animal_id")
    op.execute("DROP INDEX IF EXISTS idx_animal_is_critical")
    op.execute("DROP INDEX IF EXISTS idx_animal_status")
    op.execute("DROP INDEX IF EXISTS idx_animal_animal_id")

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS generate_data_health_values ON data")
    op.execute("DROP TRIGGER IF EXISTS update_data_updated_at ON data")
    op.execute("DROP TRIGGER IF EXISTS update_animal_updated_at ON animal")
    op.execute("DROP TRIGGER IF EXISTS update_animals_updated_at ON animals")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS generate_random_health_values()")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
