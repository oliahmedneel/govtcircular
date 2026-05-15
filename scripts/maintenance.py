# ========================================
# JobSite — Maintenance Script
# ========================================
"""
Maintenance and utility commands for JobSite.

Usage:
  python scripts/maintenance.py stats       # Show processing statistics
  python scripts/maintenance.py clean       # Clean up old log files
  python scripts/maintenance.py reset-db    # Reset database (keeps files)
  python scripts/maintenance.py build       # Build Hugo site
"""

import os
import sys
import argparse
import shutil
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.logger import get_logger
from app.utils import load_config, get_project_root
from app.database import Database
from app.git_deployer import GitDeployer

logger = get_logger(__name__)


def show_stats(config: dict) -> None:
    """Display processing statistics."""
    db = Database(config)
    stats = db.get_stats()

    print("\n📊 JobSite Statistics")
    print("=" * 50)
    print(f"Total posts created: {stats.get('total_posts', 0)}")
    print()

    print("By Status:")
    for status, count in stats.get("by_status", {}).items():
        print(f"  {status}: {count}")

    print("\nBy Category:")
    for category, count in stats.get("by_category", {}).items():
        print(f"  {category}: {count}")

    print("\nRecent Files:")
    for item in stats.get("recent", []):
        print(f"  {item['processed_at']} | {item['filename']} ({item['category']})")

    db.close()


def clean_logs(config: dict, days: int = 30) -> None:
    """
    Clean up log files older than specified days.

    Args:
        config: Configuration dictionary.
        days: Age threshold in days.
    """
    log_dir = os.path.join(
        get_project_root(),
        config.get("paths", {}).get("logs", "logs"),
    )

    if not os.path.exists(log_dir):
        print("No logs directory found.")
        return

    cutoff = datetime.now() - timedelta(days=days)
    cleaned = 0

    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
                cleaned += 1
                logger.info("Removed old log: %s", filename)

    print(f"✅ Cleaned {cleaned} old log file(s) (>{days} days)")


def reset_database(config: dict) -> None:
    """Reset the database by deleting the SQLite file."""
    data_dir = os.path.join(
        get_project_root(),
        config.get("paths", {}).get("data", "data"),
    )
    db_path = os.path.join(data_dir, "jobsite.db")

    if os.path.exists(db_path):
        backup_path = db_path + ".bak"
        shutil.copy2(db_path, backup_path)
        os.remove(db_path)
        print(f"✅ Database reset. Backup saved to: {backup_path}")
    else:
        print("No database found.")

    # Reinitialize
    db = Database(config)
    db.initialize()
    db.close()
    print("✅ New database created.")


def build_site(config: dict) -> None:
    """Build the Hugo site."""
    deployer = GitDeployer(config)
    success = deployer.build_hugo()
    if success:
        print("✅ Hugo site built successfully.")
    else:
        print("❌ Hugo build failed. Is Hugo installed?")


def main():
    parser = argparse.ArgumentParser(description="JobSite Maintenance")
    parser.add_argument("command", choices=["stats", "clean", "reset-db", "build"])
    parser.add_argument("--days", type=int, default=30, help="Days threshold for log cleanup")

    args = parser.parse_args()
    config = load_config()

    if args.command == "stats":
        show_stats(config)
    elif args.command == "clean":
        clean_logs(config, args.days)
    elif args.command == "reset-db":
        confirm = input("Are you sure you want to reset the database? (yes/no): ")
        if confirm.lower() == "yes":
            reset_database(config)
        else:
            print("Cancelled.")
    elif args.command == "build":
        build_site(config)


if __name__ == "__main__":
    main()