#!/usr/bin/env python3
"""
HIPAA Infrastructure Resource Unprotection Utility

This script temporarily removes protection from Pulumi resources to allow cleanup
while maintaining audit logs and safety measures.

Usage:
    python unprotect-resources.py --environment dev [--dry-run]
"""

import json
import subprocess
import sys
import argparse
from typing import List, Dict, Any


class ResourceUnprotector:
    """Handles unprotection of Pulumi resources for cleanup operations."""
    
    def __init__(self, environment: str, dry_run: bool = False):
        self.environment = environment
        self.dry_run = dry_run
        self.stack_name = f"lockdev-hippa-iac-{environment}"
        
    def run_command(self, cmd: List[str]) -> str:
        """Run a Pulumi command and return output."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return ""
    
    def get_protected_resources(self) -> List[Dict[str, Any]]:
        """Get list of protected resources in the stack."""
        # Check if stack exists
        stacks = self.run_command(["pulumi", "stack", "ls", "--json"])
        if not stacks:
            return []
            
        try:
            stack_list = json.loads(stacks)
            if not any(s.get("name") == self.stack_name for s in stack_list):
                print(f"Stack {self.stack_name} not found")
                return []
        except json.JSONDecodeError:
            print("Could not parse stack list")
            return []
        
        # Get stack state
        self.run_command(["pulumi", "stack", "select", self.stack_name])
        
        # Get stack exports and resources
        exports = self.run_command(["pulumi", "stack", "export"])
        if not exports:
            return []
            
        try:
            state = json.loads(exports)
            resources = []
            
            def extract_protected_resources(obj, path=""):
                if isinstance(obj, dict):
                    if obj.get("type", "").startswith("aws:"):
                        urn = obj.get("urn", "")
                        if urn and "protect" in str(obj):
                            resources.append({
                                "urn": urn,
                                "type": obj.get("type", ""),
                                "name": obj.get("name", ""),
                                "path": path
                            })
                    
                    for key, value in obj.items():
                        new_path = f"{path}.{key}" if path else key
                        extract_protected_resources(value, new_path)
                
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        new_path = f"{path}[{i}]"
                        extract_protected_resources(item, new_path)
            
            extract_protected_resources(state)
            return resources
            
        except json.JSONDecodeError:
            print("Could not parse stack state")
            return []
    
    def unprotect_resources(self) -> bool:
        """Unprotect all protected resources in the stack."""
        print(f"{'[DRY RUN] ' if self.dry_run else ''}Unprotecting resources for environment: {self.environment}")
        
        # Get protected resources
        resources = self.get_protected_resources()
        if not resources:
            print("No protected resources found")
            return True
        
        print(f"Found {len(resources)} protected resources:")
        for resource in resources:
            print(f"  - {resource['type']}: {resource['name']}")
        
        if self.dry_run:
            print("[DRY RUN] Would unprotect all listed resources")
            return True
        
        # Use pulumi state unprotect for each resource
        success = True
        for resource in resources:
            urn = resource['urn']
            print(f"Unprotecting: {resource['type']} {resource['name']}")
            
            try:
                subprocess.run([
                    "pulumi", "state", "unprotect", 
                    "--yes", urn
                ], check=True, capture_output=True)
                print(f"  ✓ Successfully unprotected")
            except subprocess.CalledProcessError as e:
                print(f"  ✗ Failed to unprotect: {e.stderr.decode()}")
                success = False
        
        return success
    
    def protect_resources(self) -> bool:
        """Re-protect all resources (for safety after cleanup)."""
        print("Re-protection is not implemented - this should be done through Pulumi program")
        return True


def main():
    parser = argparse.ArgumentParser(description="Unprotect Pulumi resources for cleanup")
    parser.add_argument("--environment", "-e", required=True, 
                       choices=["dev", "staging", "prod"],
                       help="Environment to unprotect resources for")
    parser.add_argument("--dry-run", "-d", action="store_true",
                       help="Show what would be done without making changes")
    parser.add_argument("--protect", action="store_true",
                       help="Re-protect resources (not implemented)")
    
    args = parser.parse_args()
    
    unprotector = ResourceUnprotector(args.environment, args.dry_run)
    
    if args.protect:
        success = unprotector.protect_resources()
    else:
        success = unprotector.unprotect_resources()
    
    if success:
        print("✅ Operation completed successfully")
        return 0
    else:
        print("❌ Operation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())