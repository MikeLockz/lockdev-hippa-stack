"""Test networking module."""
import pytest
import pulumi
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pulumi.runtime.test
def test_vpc_creation():
    """Test VPC creation."""
    from networking.vpc import create_vpc
    
    vpc_resources = create_vpc()
    
    assert vpc_resources["vpc"] is not None
    assert len(vpc_resources["public_subnets"]) == 2
    assert len(vpc_resources["private_subnets"]) == 2
    assert vpc_resources["internet_gateway"] is not None
    assert vpc_resources["nat_gateway"] is not None