"""
Query OTEL tables from VastDB and print sample records.

Usage:
    export VASTDB_ENDPOINT=http://vastdb:8080
    export VASTDB_ACCESS_KEY=your_access_key
    export VASTDB_SECRET_KEY=your_secret_key
    
    python query_otel_tables.py
"""

import os
import vastdb
from vastdb.config import QueryConfig


# Configuration
VASTDB_ENDPOINT = os.getenv("VASTDB_ENDPOINT")
VASTDB_ACCESS_KEY = os.getenv("VASTDB_ACCESS_KEY")
VASTDB_SECRET_KEY = os.getenv("VASTDB_SECRET_KEY")
VASTDB_BUCKET = os.getenv("VASTDB_BUCKET", "observability")
VASTDB_SCHEMA = os.getenv("VASTDB_SCHEMA", "otel")

# Tables to query
TABLES = [
    "logs_otel_analytic",
    "metrics_otel_analytic",
    "traces_otel_analytic",
    "span_events_otel_analytic",
    "span_links_otel_analytic",
]


def query_table(session, bucket_name, schema_name, table_name, limit=1):
    """Query a table and return as pandas DataFrame."""
    with session.transaction() as tx:
        bucket = tx.bucket(bucket_name)
        schema = bucket.schema(schema_name, fail_if_missing=True)
        table = schema.table(table_name, fail_if_missing=False)
        
        if table is None:
            return None
        
        config = QueryConfig(
            num_splits=1,
            num_sub_splits=1,
            limit_rows_per_sub_split=limit,
        )
        
        # Must read and convert within the transaction
        #batches = list(table.select(config=config))
        batches = list(table.select(limit_rows=limit))
        
        if not batches:
            return None
        
        # Convert to pandas inside the transaction
        return batches[0].to_pandas()


def main():
    # Connect
    print(f"Connecting to VastDB at {VASTDB_ENDPOINT}...")
    session = vastdb.connect(
        endpoint=VASTDB_ENDPOINT,
        access=VASTDB_ACCESS_KEY,
        secret=VASTDB_SECRET_KEY
    )
    print("Connected!\n")
    
    # Query each table
    for table_name in TABLES:
        print("=" * 80)
        print(f"TABLE: {VASTDB_SCHEMA}.{table_name}")
        print("=" * 80)
        
        try:
            df = query_table(session, VASTDB_BUCKET, VASTDB_SCHEMA, table_name, limit=1)
            
            if df is None:
                print("  (table not found or empty)\n")
                continue
            
            if df.empty:
                print("  (no records)\n")
                continue
            
            print(f"  Rows: {len(df)}, Columns: {list(df.columns)}\n")
            
            # Print each row
            for idx, row in df.iterrows():
                print(f"  --- Record {idx + 1} ---")
                for col in df.columns:
                    value = row[col]
                    # Truncate long values
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    print(f"    {col}: {value_str}")
                print()
        
        except Exception as e:
            print(f"  Error: {type(e).__name__}: {e}\n")
    
    print("Done.")


if __name__ == "__main__":
    main()
