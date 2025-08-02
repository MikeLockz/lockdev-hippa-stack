#!/usr/bin/env python3
"""
Draw.io Diagram Generation Utilities
Provides common functionality for creating draw.io XML diagrams
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import logging

logger = logging.getLogger(__name__)

class DrawIOGenerator:
    """Utility class for generating draw.io XML diagrams"""
    
    def __init__(self, output_dir="./output"):
        self.output_dir = output_dir
        
    def create_mxfile(self, diagram_name, diagram_id):
        """Create the root mxfile element"""
        mxfile = ET.Element('mxfile')
        mxfile.set('host', 'app.diagrams.net')
        mxfile.set('modified', '2024-01-01')
        mxfile.set('agent', '5.0')
        mxfile.set('etag', diagram_name.lower().replace(' ', '_'))
        mxfile.set('version', '21.1.2')
        mxfile.set('type', 'device')
        return mxfile
    
    def create_diagram(self, mxfile, name, diagram_id):
        """Create diagram element"""
        diagram = ET.SubElement(mxfile, 'diagram')
        diagram.set('name', name)
        diagram.set('id', diagram_id)
        return diagram
    
    def create_graph_model(self, diagram):
        """Create mxGraphModel element"""
        mxgraphmodel = ET.SubElement(diagram, 'mxGraphModel')
        mxgraphmodel.set('dx', '1422')
        mxgraphmodel.set('dy', '794')
        mxgraphmodel.set('grid', '1')
        mxgraphmodel.set('gridSize', '10')
        mxgraphmodel.set('guides', '1')
        mxgraphmodel.set('tooltips', '1')
        mxgraphmodel.set('connect', '1')
        mxgraphmodel.set('arrows', '1')
        mxgraphmodel.set('fold', '1')
        mxgraphmodel.set('page', '1')
        mxgraphmodel.set('pageScale', '1')
        mxgraphmodel.set('pageWidth', '827')
        mxgraphmodel.set('pageHeight', '1169')
        mxgraphmodel.set('math', '0')
        mxgraphmodel.set('shadow', '0')
        return mxgraphmodel
    
    def create_root(self, mxgraphmodel):
        """Create root element"""
        root = ET.SubElement(mxgraphmodel, 'root')
        ET.SubElement(root, 'mxCell', id='0')
        ET.SubElement(root, 'mxCell', id='1', parent='0')
        return root
    
    def add_rectangle(self, root, id, label, x, y, width, height, 
                     fill_color="#dae8fc", stroke_color="#6c8ebf", parent="1"):
        """Add a rectangle shape"""
        cell = ET.SubElement(root, 'mxCell', id=id)
        cell.set('value', label)
        cell.set('style', f'rounded=1;whiteSpace=wrap;html=1;fillColor={fill_color};strokeColor={stroke_color};')
        cell.set('vertex', '1')
        cell.set('parent', parent)
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(width), height=str(height))
        return cell
    
    def add_swimlane(self, root, id, label, x, y, width, height, 
                    fill_color="#e1d5e7", stroke_color="#9673a6"):
        """Add a swimlane container"""
        cell = ET.SubElement(root, 'mxCell', id=id)
        cell.set('value', label)
        cell.set('style', 'swimlane;horizontal=0;startSize=23;fillColor=#e1d5e7;strokeColor=#9673a6;')
        cell.set('vertex', '1')
        cell.set('parent', '1')
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(width), height=str(height))
        return cell
    
    def add_cylinder(self, root, id, label, x, y, width, height, 
                    fill_color="#e1d5e7", stroke_color="#9673a6", parent="1"):
        """Add a cylinder shape (for databases/storage)"""
        cell = ET.SubElement(root, 'mxCell', id=id)
        cell.set('value', label)
        cell.set('style', f'shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15;fillColor={fill_color};strokeColor={stroke_color};')
        cell.set('vertex', '1')
        cell.set('parent', parent)
        ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(width), height=str(height))
        return cell
    
    def add_edge(self, root, id, source, target, parent="1"):
        """Add an edge/connection between elements"""
        edge = ET.SubElement(root, 'mxCell', id=id)
        edge.set('style', 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;')
        edge.set('edge', '1')
        edge.set('parent', parent)
        edge.set('source', source)
        edge.set('target', target)
        return edge
    
    def save_drawio_file(self, mxfile, filename):
        """Save the draw.io XML to file"""
        filepath = os.path.join(self.output_dir, filename)
        
        # Convert to pretty XML
        xml_str = minidom.parseString(ET.tostring(mxfile)).toprettyxml(indent='  ')
        
        # Write to file
        with open(filepath, 'w') as f:
            f.write(xml_str)
        
        logger.info(f"✅ Draw.io diagram saved: {filepath}")
        return filepath
    
    def create_network_architecture(self, filename="network_architecture.drawio"):
        """Create a complete network architecture diagram"""
        # Create base structure
        mxfile = self.create_mxfile("HIPAA Network Architecture", "network_arch")
        diagram = self.create_diagram(mxfile, "HIPAA Network Architecture", "network_arch")
        mxgraphmodel = self.create_graph_model(diagram)
        root = self.create_root(mxgraphmodel)
        
        # Internet Gateway
        self.add_rectangle(root, "internet", "Internet Gateway", 350, 50, 120, 60)
        
        # VPC Container
        vpc = self.add_swimlane(root, "vpc", "HIPAA VPC (10.0.0.0/16)", 50, 150, 700, 400)
        
        # Public Subnets
        self.add_rectangle(root, "public1", "Public Subnet 1\n(10.0.1.0/24)\nus-east-1a", 
                          50, 50, 150, 80, parent="vpc")
        self.add_rectangle(root, "public2", "Public Subnet 2\n(10.0.2.0/24)\nus-east-1b", 
                          220, 50, 150, 80, parent="vpc")
        
        # Private Subnets
        self.add_rectangle(root, "private1", "Private Subnet 1\n(10.0.3.0/24)\nus-east-1a", 
                          50, 150, 150, 80, fill_color="#d5e8d4", stroke_color="#82b366", parent="vpc")
        self.add_rectangle(root, "private2", "Private Subnet 2\n(10.0.4.0/24)\nus-east-1b", 
                          220, 150, 150, 80, fill_color="#d5e8d4", stroke_color="#82b366", parent="vpc")
        
        # Load Balancer
        self.add_rectangle(root, "alb", "Application Load Balancer", 
                          400, 70, 120, 60, fill_color="#f8cecc", stroke_color="#b85450", parent="vpc")
        
        # ECS Cluster
        self.add_rectangle(root, "ecs", "ECS Cluster", 
                          400, 170, 120, 60, parent="vpc")
        
        # RDS Database
        self.add_cylinder(root, "rds", "RDS PostgreSQL\n(Multi-AZ)", 
                         580, 140, 100, 80, parent="vpc")
        
        # S3 Logs
        self.add_cylinder(root, "s3", "S3 Logs Bucket", 
                         580, 250, 100, 80, fill_color="#fff2cc", stroke_color="#d6b656", parent="vpc")
        
        # Connections
        self.add_edge(root, "edge1", "internet", "alb")
        self.add_edge(root, "edge2", "alb", "ecs", parent="vpc")
        self.add_edge(root, "edge3", "ecs", "rds", parent="vpc")
        
        return self.save_drawio_file(mxfile, filename)

# Color schemes for different diagram types
COLORS = {
    'network': {
        'internet': '#dae8fc',
        'vpc': '#e1d5e7',
        'public_subnet': '#fff2cc',
        'private_subnet': '#d5e8d4',
        'load_balancer': '#f8cecc',
        'compute': '#dae8fc',
        'database': '#e1d5e7',
        'storage': '#fff2cc'
    },
    'security': {
        'firewall': '#f8cecc',
        'encryption': '#e1d5e7',
        'identity': '#dae8fc',
        'monitoring': '#fff2cc'
    },
    'compute': {
        'container': '#dae8fc',
        'cluster': '#e1d5e7',
        'service': '#fff2cc',
        'registry': '#d5e8d4'
    },
    'observability': {
        'logs': '#fff2cc',
        'metrics': '#d5e8d4',
        'alerts': '#f8cecc',
        'dashboard': '#e1d5e7'
    }
}