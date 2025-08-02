#!/usr/bin/env python3
"""
Utility to get the current Pulumi stack name
"""

import subprocess
import json
import sys

def get_current_stack():
    """Get the current Pulumi stack name"""
    try:
        result = subprocess.run(
            ["pulumi", "stack", "ls", "--json"],
            capture_output=True,
            text=True,
            cwd="../"
        )
        
        if result.returncode != 0:
            return "test"  # Default fallback
        
        stacks = json.loads(result.stdout)
        
        # Find current stack
        for stack in stacks:
            if stack.get('current', False):
                return stack.get('name', 'test')
        
        # If no current stack, return first one
        if stacks:
            return stacks[0].get('name', 'test')
        
        return "test"  # Default fallback
        
    except Exception:
        return "test"  # Default fallback

if __name__ == "__main__":
    print(get_current_stack())