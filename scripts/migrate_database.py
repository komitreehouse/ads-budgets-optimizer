#!/usr/bin/env python3
"""
Migrate database to add platform_entity_ids column to arms table.

This script updates the existing database schema to match the current models.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.bandit_ads.database import get_db_manager
from sqlalchemy import text
from src.bandit_ads.utils import get_logger

logger = get_logger('migrate')


def migrate_arms_table():
    """Add platform_entity_ids column to arms table if it doesn't exist."""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        try:
            # Check if column exists
            result = session.execute(text(
                "PRAGMA table_info(arms)"
            ))
            columns = [row[1] for row in result]
            
            if 'platform_entity_ids' in columns:
                logger.info("Column 'platform_entity_ids' already exists in arms table")
            else:
                # Add the column
                logger.info("Adding 'platform_entity_ids' column to arms table...")
                session.execute(text(
                    "ALTER TABLE arms ADD COLUMN platform_entity_ids TEXT"
                ))
                session.commit()
                logger.info("✅ Successfully added 'platform_entity_ids' column")
            
            return True
            
        except Exception as e:
            logger.error(f"Error migrating arms table: {str(e)}")
            session.rollback()
            return False


def migrate_campaigns_table():
    """Add campaign settings columns to campaigns table if they don't exist."""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        try:
            # Check existing columns
            result = session.execute(text(
                "PRAGMA table_info(campaigns)"
            ))
            columns = [row[1] for row in result]
            
            new_columns = {
                'primary_kpi': 'TEXT DEFAULT "ROAS"',
                'target_roas': 'REAL',
                'target_cpa': 'REAL',
                'target_revenue': 'REAL',
                'target_conversions': 'INTEGER',
                'benchmark_roas': 'REAL',
                'benchmark_cpa': 'REAL',
                'benchmark_revenue': 'REAL',
                'benchmark_conversions': 'INTEGER',
                'scaling_threshold': 'REAL DEFAULT 1.1',
                'stable_threshold': 'REAL DEFAULT 0.9'
            }
            
            added = False
            for col_name, col_def in new_columns.items():
                if col_name not in columns:
                    logger.info(f"Adding '{col_name}' column to campaigns table...")
                    session.execute(text(
                        f"ALTER TABLE campaigns ADD COLUMN {col_name} {col_def}"
                    ))
                    added = True
            
            if added:
                session.commit()
                logger.info("✅ Successfully added campaign settings columns")
            else:
                logger.info("✅ All campaign settings columns already exist")
            
            return True
            
        except Exception as e:
            logger.error(f"Error migrating campaigns table: {str(e)}")
            session.rollback()
            return False


def recreate_database():
    """Drop and recreate all tables (WARNING: This deletes all data!)."""
    db_manager = get_db_manager()
    
    logger.warning("Dropping all tables...")
    db_manager.drop_tables()
    
    logger.info("Creating tables with new schema...")
    db_manager.create_tables()
    
    logger.info("✅ Database recreated successfully")


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate database schema")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate all tables (WARNING: deletes all data!)"
    )
    
    args = parser.parse_args()
    
    if args.recreate:
        print("⚠️  WARNING: This will delete all data in the database!")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled")
            return 0
        recreate_database()
    else:
        print("Migrating database schema...")
        success = True
        success = success and migrate_arms_table()
        success = success and migrate_campaigns_table()
        
        if success:
            print("✅ Migration completed successfully")
        else:
            print("❌ Migration failed")
            print("\nIf migration fails, you can recreate the database:")
            print("  python scripts/migrate_database.py --recreate")
            print("  (WARNING: This will delete all existing data)")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
