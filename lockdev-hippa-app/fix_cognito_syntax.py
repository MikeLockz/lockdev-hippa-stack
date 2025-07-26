#!/usr/bin/env python3
"""
Fix syntax issues in the Cognito provider file.
"""

import re

def fix_cognito_syntax():
    """Fix dictionary unpacking syntax issues in the Cognito provider."""
    
    with open('src/auth/providers/cognito.py', 'r') as f:
        content = f.read()
    
    # Pattern to match problematic dictionary unpacking
    pattern = r'client_info_with_metadata = \(client_info or \{\}\)\.copy\(\); client_info_with_metadata\.update\(([^}]+)\}'
    
    def replace_func(match):
        key_value = match.group(1)
        # Extract the key and value from something like "'error': str(error)"
        if ':' in key_value:
            parts = key_value.split(':', 1)
            key = parts[0].strip().strip("'\"")
            value = parts[1].strip()
            return f"audit_metadata = (client_info or {{}}).copy(); audit_metadata['{key}'] = {value}; audit_metadata"
        return match.group(0)
    
    # Replace all problematic patterns
    content = re.sub(pattern, replace_func, content)
    
    # Also fix remaining simple cases
    content = re.sub(
        r'client_info_with_metadata = \(client_info or \{\}\)\.copy\(\); client_info_with_metadata\.update\(',
        'audit_metadata = (client_info or {}).copy(); audit_metadata.update({',
        content
    )
    
    with open('src/auth/providers/cognito.py', 'w') as f:
        f.write(content)
    
    print("Fixed syntax issues in cognito.py")

if __name__ == '__main__':
    fix_cognito_syntax()