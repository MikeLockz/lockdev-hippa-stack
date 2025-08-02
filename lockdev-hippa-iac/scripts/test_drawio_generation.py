#!/usr/bin/env python3
"""
Test script to validate draw.io file generation across all diagram phases
"""

import os
import sys
import subprocess
import xml.etree.ElementTree as ET

# Add the scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drawio_utils import DrawIOGenerator

def test_drawio_format(filepath):
    """Test if a file is valid draw.io XML format"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Check for required draw.io elements
        if root.tag != 'mxfile':
            return False, "Root element is not 'mxfile'"
        
        # Check for diagram element
        diagrams = root.findall('.//diagram')
        if not diagrams:
            return False, "No diagram elements found"
        
        # Check for mxGraphModel
        models = root.findall('.//mxGraphModel')
        if not models:
            return False, "No mxGraphModel elements found"
        
        return True, "Valid draw.io format"
    except ET.ParseError as e:
        return False, f"XML parse error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def test_generation():
    """Test draw.io generation for all diagram types"""
    output_dir = "./output"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print("🧪 Testing Draw.io File Generation")
    print("=" * 40)
    
    # Test the utility directly
    drawio_gen = DrawIOGenerator(output_dir)
    
    test_cases = [
        ("Network Architecture", "network_architecture.drawio"),
        ("Compute Architecture", "compute_architecture.drawio"),
        ("Security Architecture", "security_architecture.drawio"),
        ("Data Flow Architecture", "dataflow_architecture.drawio"),
        ("CI/CD Pipeline", "cicd_pipeline.drawio"),
        ("Observability", "observability_architecture.drawio"),
        ("Disaster Recovery", "disaster_recovery_architecture.drawio")
    ]
    
    results = []
    
    for name, filename in test_cases:
        filepath = os.path.join(output_dir, filename)
        
        print(f"\n📊 Testing {name}...")
        
        # Generate using the appropriate method
        if "network" in filename:
            drawio_gen.create_network_architecture(filename)
        else:
            # For other types, create basic structure
            mxfile = drawio_gen.create_mxfile(name, name.lower().replace(" ", "_"))
            diagram = drawio_gen.create_diagram(mxfile, name, name.lower().replace(" ", "_"))
            mxgraphmodel = drawio_gen.create_graph_model(diagram)
            root = drawio_gen.create_root(mxgraphmodel)
            
            # Add some basic elements
            drawio_gen.add_rectangle(root, "test1", f"{name} Component 1", 100, 100, 150, 60)
            drawio_gen.add_rectangle(root, "test2", f"{name} Component 2", 300, 100, 150, 60)
            drawio_gen.add_edge(root, "edge1", "test1", "test2")
            
            drawio_gen.save_drawio_file(mxfile, filename)
        
        # Validate the generated file
        if os.path.exists(filepath):
            is_valid, message = test_drawio_format(filepath)
            if is_valid:
                print(f"   ✅ {filename}: {message}")
                results.append(True)
            else:
                print(f"   ❌ {filename}: {message}")
                results.append(False)
        else:
            print(f"   ❌ {filename}: File not generated")
            results.append(False)
    
    # Summary
    print("\n📋 Test Results Summary")
    print("=" * 25)
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All draw.io files generated successfully!")
        return 0
    else:
        print("⚠️  Some draw.io files failed validation")
        return 1

def test_existing_files():
    """Test existing draw.io files in output directory"""
    output_dir = "./output"
    
    print("\n🔍 Testing Existing Draw.io Files")
    print("=" * 35)
    
    if not os.path.exists(output_dir):
        print("❌ Output directory does not exist")
        return 1
    
    drawio_files = [f for f in os.listdir(output_dir) if f.endswith('.drawio')]
    
    if not drawio_files:
        print("⚠️  No .drawio files found in output directory")
        return 1
    
    results = []
    for filename in drawio_files:
        filepath = os.path.join(output_dir, filename)
        is_valid, message = test_drawio_format(filepath)
        
        if is_valid:
            print(f"   ✅ {filename}: {message}")
            results.append(True)
        else:
            print(f"   ❌ {filename}: {message}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    print(f"\nValidation Results: {passed}/{total} files passed")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--existing":
        exit(test_existing_files())
    else:
        exit(test_generation())