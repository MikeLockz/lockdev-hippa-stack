"""VPC configuration for HIPAA compliant infrastructure."""
import pulumi
import pulumi_aws as aws
from typing import Dict, Any


def create_vpc() -> Dict[str, Any]:
    """Create VPC with proper HIPAA compliance settings."""
    config = pulumi.Config()
    
    # Create VPC
    vpc = aws.ec2.Vpc(
        "hipaa-vpc",
        cidr_block="10.0.0.0/16",
        enable_dns_hostnames=True,
        enable_dns_support=True,
        tags={
            "Name": "HIPAA-VPC",
            "Environment": config.get("environment", "dev"),
            "Compliance": "HIPAA"
        }
    )
    
    # Create Internet Gateway
    igw = aws.ec2.InternetGateway(
        "hipaa-igw",
        vpc_id=vpc.id,
        tags={
            "Name": "HIPAA-IGW",
            "Environment": config.get("environment", "dev")
        }
    )
    
    # Create public subnets
    public_subnet_1 = aws.ec2.Subnet(
        "public-subnet-1",
        vpc_id=vpc.id,
        cidr_block="10.0.1.0/24",
        availability_zone="us-east-1a",
        map_public_ip_on_launch=True,
        tags={
            "Name": "Public-Subnet-1",
            "Type": "Public",
            "Environment": config.get("environment", "dev")
        }
    )
    
    public_subnet_2 = aws.ec2.Subnet(
        "public-subnet-2",
        vpc_id=vpc.id,
        cidr_block="10.0.2.0/24",
        availability_zone="us-east-1b",
        map_public_ip_on_launch=True,
        tags={
            "Name": "Public-Subnet-2",
            "Type": "Public",
            "Environment": config.get("environment", "dev")
        }
    )
    
    # Create private subnets
    private_subnet_1 = aws.ec2.Subnet(
        "private-subnet-1",
        vpc_id=vpc.id,
        cidr_block="10.0.3.0/24",
        availability_zone="us-east-1a",
        tags={
            "Name": "Private-Subnet-1",
            "Type": "Private",
            "Environment": config.get("environment", "dev")
        }
    )
    
    private_subnet_2 = aws.ec2.Subnet(
        "private-subnet-2",
        vpc_id=vpc.id,
        cidr_block="10.0.4.0/24",
        availability_zone="us-east-1b",
        tags={
            "Name": "Private-Subnet-2",
            "Type": "Private",
            "Environment": config.get("environment", "dev")
        }
    )
    
    # Create NAT Gateway
    nat_eip = aws.ec2.Eip(
        "nat-eip",
        domain="vpc",
        tags={
            "Name": "NAT-EIP",
            "Environment": config.get("environment", "dev")
        }
    )
    
    nat_gateway = aws.ec2.NatGateway(
        "nat-gateway",
        allocation_id=nat_eip.id,
        subnet_id=public_subnet_1.id,
        tags={
            "Name": "NAT-Gateway",
            "Environment": config.get("environment", "dev")
        }
    )
    
    # Create route tables
    public_route_table = aws.ec2.RouteTable(
        "public-route-table",
        vpc_id=vpc.id,
        tags={
            "Name": "Public-Route-Table",
            "Environment": config.get("environment", "dev")
        }
    )
    
    private_route_table = aws.ec2.RouteTable(
        "private-route-table",
        vpc_id=vpc.id,
        tags={
            "Name": "Private-Route-Table",
            "Environment": config.get("environment", "dev")
        }
    )
    
    # Create routes
    aws.ec2.Route(
        "public-route",
        route_table_id=public_route_table.id,
        destination_cidr_block="0.0.0.0/0",
        gateway_id=igw.id
    )
    
    aws.ec2.Route(
        "private-route",
        route_table_id=private_route_table.id,
        destination_cidr_block="0.0.0.0/0",
        nat_gateway_id=nat_gateway.id
    )
    
    # Associate subnets with route tables
    aws.ec2.RouteTableAssociation(
        "public-subnet-1-association",
        subnet_id=public_subnet_1.id,
        route_table_id=public_route_table.id
    )
    
    aws.ec2.RouteTableAssociation(
        "public-subnet-2-association",
        subnet_id=public_subnet_2.id,
        route_table_id=public_route_table.id
    )
    
    aws.ec2.RouteTableAssociation(
        "private-subnet-1-association",
        subnet_id=private_subnet_1.id,
        route_table_id=private_route_table.id
    )
    
    aws.ec2.RouteTableAssociation(
        "private-subnet-2-association",
        subnet_id=private_subnet_2.id,
        route_table_id=private_route_table.id
    )
    
    return {
        "vpc": vpc,
        "public_subnets": [public_subnet_1, public_subnet_2],
        "private_subnets": [private_subnet_1, private_subnet_2],
        "internet_gateway": igw,
        "nat_gateway": nat_gateway,
        "public_route_table": public_route_table,
        "private_route_table": private_route_table
    }