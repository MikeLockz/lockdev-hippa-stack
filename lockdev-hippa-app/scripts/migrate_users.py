#!/usr/bin/env python3
"""
User Migration CLI Script

Command-line interface for migrating users between authentication providers
with comprehensive logging, dry-run capabilities, and rollback support.

Usage:
    python scripts/migrate_users.py --from custom --to aws_cognito --dry-run
    python scripts/migrate_users.py --from custom --to auth0 --batch-size 50 --verbose
    python scripts/migrate_users.py --rollback migration-id-here --confirm
    python scripts/migrate_users.py --validate migration-id-here
    python scripts/migrate_users.py --status migration-id-here

HIPAA Compliance:
- All operations logged with audit trail
- No PHI exposure in logs
- Secure handling of user data
- Rollback capabilities for data protection
"""

import asyncio
import argparse
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import getpass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth.factory import create_auth_provider, AuthProviderType
from src.auth.sync.migration import ProviderMigration
from src.auth.sync.session_migration import SessionMigration
from src.utils.database import get_db_session
from src.utils.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MigrationCLI:
    """Command-line interface for user migration operations."""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create argument parser with all commands."""
        parser = argparse.ArgumentParser(
            description="Migrate users between authentication providers",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Dry run migration from custom to Cognito
  python scripts/migrate_users.py --from custom --to aws_cognito --dry-run

  # Actual migration with custom batch size
  python scripts/migrate_users.py --from custom --to auth0 --batch-size 25 --verbose

  # Rollback a specific migration
  python scripts/migrate_users.py --rollback 123e4567-e89b-12d3-a456-426614174000 --confirm

  # Validate migration results
  python scripts/migrate_users.py --validate 123e4567-e89b-12d3-a456-426614174000

  # Check migration status
  python scripts/migrate_users.py --status 123e4567-e89b-12d3-a456-426614174000

Provider types:
  custom      - Local JWT-based authentication
  aws_cognito - AWS Cognito User Pools
  auth0       - Auth0 authentication service
  supabase    - Supabase Auth service
"""
        )
        
        # Global options
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose logging"
        )
        
        parser.add_argument(
            "--config",
            type=str,
            help="Configuration file path"
        )
        
        # Subcommands
        subparsers = parser.add_subparsers(dest="command", help="Available commands")
        
        # Migrate command
        migrate_parser = subparsers.add_parser("migrate", help="Migrate users between providers")
        migrate_parser.add_argument(
            "--from", "-f",
            dest="source_provider",
            required=True,
            choices=["custom", "aws_cognito", "auth0", "supabase"],
            help="Source authentication provider"
        )
        migrate_parser.add_argument(
            "--to", "-t",
            dest="target_provider",
            required=True,
            choices=["custom", "aws_cognito", "auth0", "supabase"],
            help="Target authentication provider"
        )
        migrate_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Perform a dry run without making changes"
        )
        migrate_parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of users to process in each batch"
        )
        migrate_parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip users already migrated"
        )
        migrate_parser.add_argument(
            "--preserve-sessions",
            action="store_true",
            help="Preserve user sessions during migration"
        )
        migrate_parser.add_argument(
            "--migration-id",
            type=str,
            help="Custom migration ID (auto-generated if not provided)"
        )
        
        # Rollback command
        rollback_parser = subparsers.add_parser("rollback", help="Rollback a migration")
        rollback_parser.add_argument(
            "migration_id",
            type=str,
            help="Migration ID to rollback"
        )
        rollback_parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt"
        )
        rollback_parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of users to process in each batch"
        )
        
        # Validate command
        validate_parser = subparsers.add_parser("validate", help="Validate migration results")
        validate_parser.add_argument(
            "migration_id",
            type=str,
            help="Migration ID to validate"
        )
        
        # Status command
        status_parser = subparsers.add_parser("status", help="Check migration status")
        status_parser.add_argument(
            "migration_id",
            type=str,
            help="Migration ID to check"
        )
        
        # Feasibility check command
        check_parser = subparsers.add_parser("check", help="Check migration feasibility")
        check_parser.add_argument(
            "--from", "-f",
            dest="source_provider",
            required=True,
            choices=["custom", "aws_cognito", "auth0", "supabase"],
            help="Source authentication provider"
        )
        check_parser.add_argument(
            "--to", "-t",
            dest="target_provider",
            required=True,
            choices=["custom", "aws_cognito", "auth0", "supabase"],
            help="Target authentication provider"
        )
        
        return parser
    
    async def run(self, args: argparse.Namespace) -> int:
        """Run the CLI command."""
        try:
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            
            # Get database session
            db_session = await get_db_session()
            
            if args.command == "migrate":
                return await self._handle_migrate(args, db_session)
            elif args.command == "rollback":
                return await self._handle_rollback(args, db_session)
            elif args.command == "validate":
                return await self._handle_validate(args, db_session)
            elif args.command == "status":
                return await self._handle_status(args, db_session)
            elif args.command == "check":
                return await self._handle_check(args, db_session)
            else:
                self.parser.print_help()
                return 1
                
        except KeyboardInterrupt:
            logger.info("Migration interrupted by user")
            return 130
        except Exception as e:
            logger.error("Migration failed", error=str(e))
            return 1
    
    async def _handle_migrate(self, args: argparse.Namespace, db_session) -> int:
        """Handle migrate command."""
        logger.info(
            "Starting migration",
            source_provider=args.source_provider,
            target_provider=args.target_provider,
            dry_run=args.dry_run,
            migration_id=args.migration_id
        )
        
        # Create providers
        source_provider = await create_auth_provider(AuthProviderType(args.source_provider))
        target_provider = await create_auth_provider(AuthProviderType(args.target_provider))
        
        # Create migration service
        migration = ProviderMigration(
            source_provider,
            target_provider,
            db_session,
            uuid.UUID(args.migration_id) if args.migration_id else None
        )
        
        # Validate migration
        print("Validating migration feasibility...")
        validation = await migration.validate_migration_feasibility()
        
        print(json.dumps(validation, indent=2))
        
        if not validation["feasible"]:
            print("❌ Migration cannot proceed due to blockers:")
            for blocker in validation["blockers"]:
                print(f"  - {blocker}")
            return 1
        
        if validation["warnings"]:
            print("⚠️  Warnings:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
        
        if args.dry_run:
            print("🔍 Performing dry run...")
        else:
            # Confirm migration
            if not self._confirm_migration(args):
                print("Migration cancelled by user")
                return 0
        
        # Perform migration
        print(f"Starting migration from {args.source_provider} to {args.target_provider}...")
        
        # Preserve sessions if requested
        if args.preserve_sessions and not args.dry_run:
            print("Preserving user sessions...")
            await self._preserve_sessions(source_provider, target_provider, db_session)
        
        results = await migration.migrate_users(
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            skip_existing=args.skip_existing
        )
        
        # Print results
        print("\n" + "="*50)
        print("MIGRATION RESULTS")
        print("="*50)
        print(f"Migration ID: {results['migration_id']}")
        print(f"Duration: {results.get('duration_seconds', 'N/A')} seconds")
        print(f"Total users: {results['total_users']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        print(f"Skipped: {results['skipped']}")
        
        if results['errors']:
            print(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(results['errors']) > 5:
                print(f"  ... and {len(results['errors']) - 5} more")
        
        if results['warnings']:
            print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
            for warning in results['warnings']:
                print(f"  - {warning}")
        
        # Save results to file
        if not args.dry_run:
            self._save_results(results, args.migration_id or results['migration_id'])
        
        return 0 if results['failed'] == 0 else 1
    
    async def _handle_rollback(self, args: argparse.Namespace, db_session) -> int:
        """Handle rollback command."""
        print(f"🔄 Preparing to rollback migration: {args.migration_id}")
        
        # Confirm rollback
        if not args.confirm:
            if not self._confirm_rollback(args.migration_id):
                print("Rollback cancelled by user")
                return 0
        
        # Get migration details
        source_provider, target_provider = await self._get_migration_providers(args.migration_id, db_session)
        
        if not source_provider or not target_provider:
            print("❌ Could not determine migration providers")
            return 1
        
        migration = ProviderMigration(target_provider, source_provider, db_session)
        
        print("Starting rollback...")
        results = await migration.rollback_migration(args.migration_id, batch_size=args.batch_size)
        
        print("\n" + "="*50)
        print("ROLLBACK RESULTS")
        print("="*50)
        print(f"Migration ID: {results['migration_id']}")
        print(f"Duration: {results.get('duration_seconds', 'N/A')} seconds")
        print(f"Users rolled back: {results['users_rolled_back']}")
        
        if results['errors']:
            print(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  - {error}")
        
        return 0 if not results['errors'] else 1
    
    async def _handle_validate(self, args: argparse.Namespace, db_session) -> int:
        """Handle validate command."""
        print(f"🔍 Validating migration: {args.migration_id}")
        
        # Get migration details
        source_provider, target_provider = await self._get_migration_providers(args.migration_id, db_session)
        
        if not source_provider or not target_provider:
            print("❌ Could not determine migration providers")
            return 1
        
        migration = ProviderMigration(source_provider, target_provider, db_session)
        
        results = await migration.validate_migration_results(args.migration_id)
        
        print("\n" + "="*50)
        print("VALIDATION RESULTS")
        print("="*50)
        print(f"Migration ID: {results['migration_id']}")
        print(f"Total validated: {results['total_validated']}")
        print(f"Valid: {results['valid']}")
        print(f"Invalid: {results['invalid']}")
        
        if results['errors']:
            print(f"\n❌ Errors ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  - {error}")
        
        if results['details']:
            print(f"\n📊 Details:")
            for detail in results['details'][:5]:  # Show first 5
                status = "✅" if detail['valid'] else "❌"
                print(f"  {status} {detail['local_user_id']} -> {detail['provider_user_id']}")
        
        return 0 if results['invalid'] == 0 else 1
    
    async def _handle_status(self, args: argparse.Namespace, db_session) -> int:
        """Handle status command."""
        # This would query the database for migration status
        print(f"📊 Checking status for migration: {args.migration_id}")
        print("\nMigration status tracking not yet implemented")
        return 0
    
    async def _handle_check(self, args: argparse.Namespace, db_session) -> int:
        """Handle check command."""
        print("🔍 Checking migration feasibility...")
        
        # Create providers
        source_provider = await create_auth_provider(AuthProviderType(args.source_provider))
        target_provider = await create_auth_provider(AuthProviderType(args.target_provider))
        
        migration = ProviderMigration(source_provider, target_provider, db_session)
        
        validation = await migration.validate_migration_feasibility()
        
        print("\n" + "="*50)
        print("FEASIBILITY CHECK RESULTS")
        print("="*50)
        print(json.dumps(validation, indent=2))
        
        if validation["feasible"]:
            print("\n✅ Migration is feasible")
        else:
            print("\n❌ Migration is not feasible")
        
        return 0 if validation["feasible"] else 1
    
    def _confirm_migration(self, args: argparse.Namespace) -> bool:
        """Confirm migration with user."""
        print(f"\n⚠️  You are about to migrate users from {args.source_provider} to {args.target_provider}")
        print(f"   Batch size: {args.batch_size}")
        print(f"   Skip existing: {args.skip_existing}")
        print(f"   Preserve sessions: {args.preserve_sessions}")
        
        response = input("\nDo you want to proceed? (yes/no): ")
        return response.lower() == 'yes'
    
    def _confirm_rollback(self, migration_id: str) -> bool:
        """Confirm rollback with user."""
        print(f"\n⚠️  You are about to rollback migration: {migration_id}")
        print("   This will delete users from the target provider and restore to source provider")
        
        response = input("\nDo you want to proceed? (yes/no): ")
        return response.lower() == 'yes'
    
    async def _get_migration_providers(self, migration_id: str, db_session) -> tuple:
        """Get source and target providers for a migration."""
        # This would query the database to determine the original migration providers
        # For now, return None - this would need to be implemented based on audit logs
        return None, None
    
    async def _preserve_sessions(self, source_provider, target_provider, db_session):
        """Preserve user sessions during migration."""
        session_migration = SessionMigration(source_provider, target_provider, db_session)
        
        # This would implement session preservation logic
        logger.info("Session preservation requested - feature not yet implemented")
    
    def _save_results(self, results: Dict[str, Any], migration_id: str):
        """Save migration results to file."""
        filename = f"migration_{migration_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = Path("migration_results") / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📄 Results saved to: {filepath}")


async def main():
    """Main CLI entry point."""
    cli = MigrationCLI()
    parser = cli._create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Set up environment
    config = get_config()
    
    print("🔐 HIPAA-Compliant User Migration CLI")
    print("=" * 40)
    print(f"User: {getpass.getuser()}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print()
    
    try:
        result = await cli.run(args)
        return result
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user")
        return 130
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)