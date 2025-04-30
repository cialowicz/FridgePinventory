#!/usr/bin/env python3
"""Script to create new database migration files."""

import os
import sys
import datetime
from pathlib import Path

def create_migration(name):
    """Create a new migration file with the given name."""
    # Get the migrations directory
    current_dir = Path(__file__).parent
    migrations_dir = current_dir.parent / 'migrations'
    
    # Get the next migration number
    existing_migrations = sorted(migrations_dir.glob('*.sql'))
    if existing_migrations:
        last_migration = existing_migrations[-1]
        last_number = int(last_migration.name.split('_')[0])
        next_number = last_number + 1
    else:
        next_number = 0
    
    # Create the migration file
    migration_name = f"{next_number:03d}_{name}.sql"
    migration_path = migrations_dir / migration_name
    
    # Write the template
    with open(migration_path, 'w') as f:
        f.write(f"""-- Migration: {name}
-- Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

-- Add your SQL statements here
""")
    
    print(f"Created new migration: {migration_path}")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python create_migration.py <migration_name>")
        print("Example: python create_migration.py add_new_table")
        sys.exit(1)
    
    create_migration(sys.argv[1]) 