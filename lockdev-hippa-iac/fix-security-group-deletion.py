#!/usr/bin/env python3
"""
Script to fix security group deletion issues with RDS ENI dependencies.
This script handles the proper cleanup of RDS instances before security group deletion.
"""

import boto3
import time
import sys
from typing import List, Dict, Any

class SecurityGroupFixer:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.ec2 = boto3.client('ec2', region_name=region)
        self.rds = boto3.client('rds', region_name=region)
        
    def get_rds_instances(self) -> List[Dict[str, Any]]:
        """Get all RDS instances in the region."""
        try:
            response = self.rds.describe_db_instances()
            return response['DBInstances']
        except Exception as e:
            print(f"Error getting RDS instances: {e}")
            return []
    
    def get_security_groups(self, group_names: List[str]) -> List[Dict[str, Any]]:
        """Get security groups by name."""
        try:
            response = self.ec2.describe_security_groups(
                GroupNames=group_names
            )
            return response['SecurityGroups']
        except Exception as e:
            print(f"Error getting security groups: {e}")
            return []
    
    def get_network_interfaces(self, security_group_id: str) -> List[Dict[str, Any]]:
        """Get network interfaces attached to security group."""
        try:
            response = self.ec2.describe_network_interfaces(
                Filters=[
                    {
                        'Name': 'group-id',
                        'Values': [security_group_id]
                    }
                ]
            )
            return response['NetworkInterfaces']
        except Exception as e:
            print(f"Error getting network interfaces: {e}")
            return []
    
    def delete_rds_instance(self, instance_id: str, skip_snapshot: bool = True) -> bool:
        """Delete RDS instance and wait for completion."""
        try:
            print(f"Deleting RDS instance: {instance_id}")
            
            # First, disable deletion protection
            try:
                self.rds.modify_db_instance(
                    DBInstanceIdentifier=instance_id,
                    DeletionProtection=False,
                    ApplyImmediately=True
                )
                print("Disabled deletion protection, waiting...")
                time.sleep(30)
            except Exception as e:
                print(f"Could not disable deletion protection or not needed: {e}")
            
            # Delete the instance
            self.rds.delete_db_instance(
                DBInstanceIdentifier=instance_id,
                SkipFinalSnapshot=skip_snapshot,
                DeleteAutomatedBackups=True
            )
            
            # Wait for deletion to complete
            print("Waiting for RDS instance deletion...")
            while True:
                try:
                    response = self.rds.describe_db_instances(
                        DBInstanceIdentifier=instance_id
                    )
                    if not response['DBInstances']:
                        break
                    
                    instance = response['DBInstances'][0]
                    status = instance['DBInstanceStatus']
                    print(f"RDS instance status: {status}")
                    
                    if status in ['deleting', 'deleted']:
                        if status == 'deleted':
                            break
                    else:
                        print(f"Unexpected status: {status}")
                        
                except self.rds.exceptions.DBInstanceNotFoundFault:
                    print("RDS instance deleted successfully")
                    break
                except Exception as e:
                    print(f"Error checking RDS status: {e}")
                    break
                    
                time.sleep(30)
            
            return True
            
        except Exception as e:
            print(f"Error deleting RDS instance {instance_id}: {e}")
            return False
    
    def detach_network_interface(self, eni_id: str, attachment_id: str) -> bool:
        """Detach network interface."""
        try:
            print(f"Detaching network interface: {eni_id}")
            self.ec2.detach_network_interface(
                AttachmentId=attachment_id,
                Force=True
            )
            
            # Wait for detachment to complete
            print("Waiting for ENI detachment...")
            while True:
                try:
                    response = self.ec2.describe_network_interfaces(
                        NetworkInterfaceIds=[eni_id]
                    )
                    if not response['NetworkInterfaces']:
                        break
                    
                    eni = response['NetworkInterfaces'][0]
                    if eni['Status'] == 'available':
                        print(f"ENI {eni_id} detached successfully")
                        break
                    elif eni['Status'] == 'detaching':
                        print("ENI still detaching...")
                    else:
                        print(f"ENI status: {eni['Status']}")
                        
                except Exception as e:
                    print(f"Error checking ENI status: {e}")
                    break
                    
                time.sleep(10)
            
            return True
            
        except Exception as e:
            print(f"Error detaching ENI {eni_id}: {e}")
            return False
    
    def delete_security_group(self, group_id: str) -> bool:
        """Delete security group."""
        try:
            print(f"Deleting security group: {group_id}")
            self.ec2.delete_security_group(GroupId=group_id)
            print(f"Security group {group_id} deleted successfully")
            return True
        except Exception as e:
            print(f"Error deleting security group {group_id}: {e}")
            return False
    
    def fix_security_group_deletion(self, target_group_names: List[str] = None) -> bool:
        """Main function to fix security group deletion issues."""
        if target_group_names is None:
            target_group_names = ['hipaa-rds-sg']
        
        print("=== Fixing Security Group Deletion Issues ===")
        
        # Get RDS instances
        rds_instances = self.get_rds_instances()
        if rds_instances:
            print(f"Found {len(rds_instances)} RDS instances")
            for instance in rds_instances:
                if 'hipaa' in instance['DBInstanceIdentifier'].lower():
                    print(f"Deleting HIPAA RDS instance: {instance['DBInstanceIdentifier']}")
                    self.delete_rds_instance(instance['DBInstanceIdentifier'])
        
        # Get target security groups
        try:
            security_groups = self.get_security_groups(target_group_names)
        except Exception as e:
            print(f"Error getting security groups by name: {e}")
            # Try getting all security groups and filtering
            try:
                response = self.ec2.describe_security_groups()
                security_groups = [sg for sg in response['SecurityGroups'] 
                                 if any(name in sg['GroupName'] for name in target_group_names)]
            except Exception as e2:
                print(f"Error getting all security groups: {e2}")
                return False
        
        if not security_groups:
            print("No target security groups found")
            return True
        
        # Process each security group
        for sg in security_groups:
            group_id = sg['GroupId']
            group_name = sg['GroupName']
            
            print(f"\nProcessing security group: {group_name} ({group_id})")
            
            # Get network interfaces attached to this security group
            enis = self.get_network_interfaces(group_id)
            
            if enis:
                print(f"Found {len(enis)} network interfaces attached to {group_name}")
                
                # Detach each network interface
                for eni in enis:
                    eni_id = eni['NetworkInterfaceId']
                    if 'Attachment' in eni and eni['Attachment']:
                        attachment_id = eni['Attachment']['AttachmentId']
                        self.detach_network_interface(eni_id, attachment_id)
                    else:
                        print(f"ENI {eni_id} has no attachment, skipping detachment")
                        
                    # Wait a bit before proceeding
                    time.sleep(5)
            
            # Wait for all ENIs to be detached
            time.sleep(30)
            
            # Delete the security group
            self.delete_security_group(group_id)
        
        print("\n=== Security Group Deletion Fix Complete ===")
        return True


def main():
    """Main function to run the security group fix."""
    region = 'us-east-1'  # Change this to your region if different
    
    fixer = SecurityGroupFixer(region)
    
    # Fix security group deletion issues
    success = fixer.fix_security_group_deletion()
    
    if success:
        print("Successfully fixed security group deletion issues!")
        return 0
    else:
        print("Failed to fix security group deletion issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())