#!/usr/bin/env python3
"""
Interactive Infrastructure Diagram Generator
Lists all available Pulumi stacks and lets users select one for diagram generation
"""

import subprocess
import json
import os
import sys
from pathlib import Path
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class InteractiveDiagramGenerator:
    def __init__(self, output_dir="./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.scripts_dir = Path(__file__).parent
        
    def list_stacks(self):
        """List all available Pulumi stacks"""
        try:
            result = subprocess.run(
                ["pulumi", "stack", "ls", "--json"],
                capture_output=True,
                text=True,
                cwd=str(self.scripts_dir.parent)
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to list stacks: {result.stderr}")
                return []
            
            stacks = json.loads(result.stdout)
            return stacks
            
        except Exception as e:
            logger.error(f"Error listing stacks: {e}")
            return []
    
    def display_stacks(self, stacks):
        """Display available stacks with selection prompt"""
        if not stacks:
            print("❌ No Pulumi stacks found!")
            print("\n💡 To create a stack:")
            print("   1. cd ../")
            print("   2. pulumi stack init <stack-name>")
            print("   3. Deploy your infrastructure")
            return None
            
        print("\n📊 Available Pulumi Stacks:")
        print("=" * 40)
        
        for i, stack in enumerate(stacks, 1):
            name = stack.get('name', 'unknown')
            last_update = stack.get('lastUpdate', 'Never')
            resource_count = stack.get('resourceCount', 0)
            current = '*' if stack.get('current', False) else ' '
            
            print(f"{i}. {name}{current} - {resource_count} resources - Last: {last_update}")
            
        print("\n0. Exit")
        
        while True:
            try:
                selection = input("\n🔍 Select a stack (number): ").strip()
                if selection == '0':
                    return None
                
                idx = int(selection) - 1
                if 0 <= idx < len(stacks):
                    selected = stacks[idx]
                    return selected['name']
                else:
                    print(f"❌ Please enter a number between 1 and {len(stacks)}")
                    
            except ValueError:
                print("❌ Please enter a valid number")
                continue
    
    def generate_diagram(self, diagram_type, stack_name):
        """Generate a specific type of diagram"""
        script_map = {
            'network': 'generate_network_diagram.py',
            'compute': 'generate_compute_diagram.py',
            'security': 'generate_security_diagram.py',
            'observability': 'generate_observability_diagram.py',
            'dataflow': 'generate_dataflow_diagram.py',
            'disaster-recovery': 'generate_dr_diagram.py',
            'cicd': 'generate_cicd_diagram.py'
        }
        
        script_name = script_map.get(diagram_type)
        if not script_name:
            logger.error(f"Unknown diagram type: {diagram_type}")
            return False
            
        script_path = self.scripts_dir / script_name
        
        try:
            cmd = [sys.executable, str(script_path), '--stack', stack_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ {diagram_type.title()} diagram generated successfully")
                return True
            else:
                logger.error(f"❌ Failed to generate {diagram_type} diagram: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error running {script_name}: {e}")
            return False
    
    def generate_all_diagrams(self, stack_name):
        """Generate all types of diagrams"""
        diagrams = [
            'network',
            'compute',
            'security',
            'observability',
            'dataflow',
            'disaster-recovery',
            'cicd'
        ]
        
        print(f"\n🚀 Generating diagrams for stack: {stack_name}")
        print("=" * 50)
        
        success_count = 0
        for diagram_type in diagrams:
            print(f"\n📊 Generating {diagram_type} diagram...")
            if self.generate_diagram(diagram_type, stack_name):
                success_count += 1
        
        print(f"\n✅ Generated {success_count}/{len(diagrams)} diagram types")
        return success_count == len(diagrams)
    
    def interactive_mode(self):
        """Run interactive stack selection and diagram generation"""
        print("🖥️  HIPAA Infrastructure Diagram Generator")
        print("=" * 45)
        
        # List available stacks
        stacks = self.list_stacks()
        stack_name = self.display_stacks(stacks)
        
        if not stack_name:
            print("❌ No stack selected. Exiting.")
            return False
        
        # Ask user what to generate
        print(f"\n🔧 Selected stack: {stack_name}")
        print("\n📋 Generation Options:")
        print("1. Generate all diagrams")
        print("2. Select specific diagram types")
        print("3. Exit")
        
        while True:
            choice = input("\nSelect option (1-3): ").strip()
            
            if choice == '1':
                return self.generate_all_diagrams(stack_name)
            elif choice == '2':
                return self.select_specific_diagrams(stack_name)
            elif choice == '3':
                print("👋 Goodbye!")
                return True
            else:
                print("❌ Please enter 1, 2, or 3")
    
    def select_specific_diagrams(self, stack_name):
        """Let user select specific diagram types"""
        diagram_types = {
            '1': ('network', 'Network Architecture'),
            '2': ('compute', 'Compute & ECS'),
            '3': ('security', 'Security & Access Controls'),
            '4': ('observability', 'Observability & Monitoring'),
            '5': ('dataflow', 'Data Flow & Encryption'),
            '6': ('disaster-recovery', 'Disaster Recovery'),
            '7': ('cicd', 'CI/CD Pipeline')
        }
        
        print(f"\n📋 Select diagram types for {stack_name}:")
        print("=" * 40)
        for key, (type_id, name) in diagram_types.items():
            print(f"{key}. {name}")
        print("0. Back to main menu")
        
        selected = input("\nEnter numbers (comma-separated, e.g., 1,3,5): ").strip()
        
        if selected == '0':
            return True
            
        selected_types = []
        for num in selected.split(','):
            num = num.strip()
            if num in diagram_types:
                selected_types.append(diagram_types[num][0])
        
        if not selected_types:
            print("❌ No valid selections made")
            return False
        
        print(f"\n🚀 Generating {len(selected_types)} selected diagrams...")
        success_count = 0
        for diagram_type in selected_types:
            if self.generate_diagram(diagram_type, stack_name):
                success_count += 1
        
        print(f"✅ Generated {success_count}/{len(selected_types)} diagrams")
        return success_count > 0

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Interactive Infrastructure Diagram Generator')
    parser.add_argument('--stack', help='Pulumi stack name (bypasses interactive selection)')
    parser.add_argument('--output', default='./output', help='Output directory')
    parser.add_argument('--all', action='store_true', help='Generate all diagrams')
    
    args = parser.parse_args()
    
    generator = InteractiveDiagramGenerator(args.output)
    
    if args.stack:
        # Use provided stack name
        if args.all:
            return generator.generate_all_diagrams(args.stack)
        else:
            return generator.select_specific_diagrams(args.stack)
    else:
        # Interactive mode
        return generator.interactive_mode()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)