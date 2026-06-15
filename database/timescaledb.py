from sqlalchemy import text
from sqlalchemy.orm import Session

def setup_timescaledb(session: Session):
    """
    Executes raw SQL to convert standard PostgreSQL tables into TimescaleDB hypertables.
    Must be run AFTER alembic migrations create the standard tables.
    """
    try:
        # Create hypertable for sensor_readings
        session.execute(text("SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);"))
        
        # Create hypertable for orchard_health
        session.execute(text("SELECT create_hypertable('orchard_health', 'time', if_not_exists => TRUE);"))
        
        # Set retention policies (e.g. drop raw data older than 2 years)
        session.execute(text("SELECT add_retention_policy('sensor_readings', drop_after => INTERVAL '2 years', if_not_exists => TRUE);"))
        
        # Enable compression
        session.execute(text("ALTER TABLE sensor_readings SET (timescaledb.compress, timescaledb.compress_segmentby = 'node_id');"))
        session.execute(text("SELECT add_compression_policy('sensor_readings', compress_after => INTERVAL '7 days', if_not_exists => TRUE);"))

        session.commit()
    except Exception as e:
        session.rollback()
        # In a test environment without TimescaleDB extension, this will fail.
        # We can silently ignore or log it depending on environment configs.
        print(f"TimescaleDB setup failed (this is normal in SQLite or standard PG test environments): {e}")
