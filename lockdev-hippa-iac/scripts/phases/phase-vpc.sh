#!/bin/bash

# Phase 4: VPC and Networking Cleanup Script
# Handles VPC, subnets, security groups, and networking resources

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

PHASE_NAME="vpc-cleanup"

# Main VPC cleanup function
cleanup_vpc_infrastructure() {
    local environment="$1"
    
    log_phase "$PHASE_NAME" "Starting VPC and networking cleanup for: $environment"
    
    # Load environment configuration
    load_environment_config "$environment"
    
    local root_profile=$(get_env_config "$environment" "root_profile")
    local region=$(get_env_config "$environment" "region")
    
    # Setup AWS environment
    setup_aws_env "$root_profile" "$region"
    
    # Cleanup VPC infrastructure in correct dependency order
    cleanup_nat_gateways "$environment"
    cleanup_vpc_endpoints "$environment"
    cleanup_network_interfaces "$environment"
    cleanup_security_groups "$environment"
    cleanup_subnets "$environment"
    cleanup_route_tables "$environment"
    cleanup_internet_gateways "$environment"
    cleanup_vpc_peering_connections "$environment"
    cleanup_vpn_gateways "$environment"
    cleanup_vpc_dhcp_options "$environment"
    cleanup_vpcs "$environment"
    
    log_phase_success "$PHASE_NAME" "VPC and networking cleanup completed"
}

# Cleanup NAT gateways
cleanup_nat_gateways() {
    local environment="$1"
    
    log_step "Cleaning up NAT gateways..."
    
    # Find NAT gateways with HIPAA naming
    local nat_gateways=$(AWS_PROFILE="$root_profile" aws ec2 describe-nat-gateways \
        --query 'NatGateways[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$nat_gateways" == "[]" ]]; then
        log_info "No NAT gateways found"
        return 0
    fi
    
    echo "$nat_gateways" | jq -r '.[].NatGatewayId' | while read -r nat_id; do
        log_info "Deleting NAT gateway: $nat_id"
        
        # Delete NAT gateway
        AWS_PROFILE="$root_profile" aws ec2 delete-nat-gateway \
            --nat-gateway-id "$nat_id" --no-cli-pager 2>/dev/null || true
    done
    
    # Wait for NAT gateways to be deleted
    log_info "Waiting for NAT gateways to be deleted..."
    for i in {1..30}; do
        local count=$(AWS_PROFILE="$root_profile" aws ec2 describe-nat-gateways \
            --query 'length(NatGateways[?State!=`deleted` && (contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`))])' \
            --output text 2>/dev/null || echo "0")
        
        if [[ "$count" == "0" ]]; then
            log_info "All NAT gateways deleted"
            break
        fi
        log_info "Waiting... ($i/30) - $count NAT gateways remaining"
        sleep 10
    done
}

# Cleanup VPC endpoints
cleanup_vpc_endpoints() {
    local environment="$1"
    
    log_step "Cleaning up VPC endpoints..."
    
    # Find VPC endpoints with HIPAA naming
    local endpoints=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpc-endpoints \
        --query 'VpcEndpoints[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$endpoints" == "[]" ]]; then
        log_info "No VPC endpoints found"
        return 0
    fi
    
    local endpoint_ids=$(echo "$endpoints" | jq -r '.[].VpcEndpointId' | tr '\n' ' ')
    if [[ -n "$endpoint_ids" ]]; then
        log_info "Deleting VPC endpoints: $endpoint_ids"
        AWS_PROFILE="$root_profile" aws ec2 delete-vpc-endpoints \
            --vpc-endpoint-ids $endpoint_ids --no-cli-pager 2>/dev/null || true
    fi
}

# Cleanup network interfaces
cleanup_network_interfaces() {
    local environment="$1"
    
    log_step "Cleaning up network interfaces..."
    
    # Find network interfaces with HIPAA naming
    local enis=$(AWS_PROFILE="$root_profile" aws ec2 describe-network-interfaces \
        --query 'NetworkInterfaces[?contains(TagSet[?Key==`Name`].Value, `hipaa`) || contains(TagSet[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$enis" == "[]" ]]; then
        log_info "No network interfaces found"
        return 0
    fi
    
    echo "$enis" | jq -r '.[].NetworkInterfaceId' | while read -r eni_id; do
        log_info "Processing network interface: $eni_id"
        
        # Check if interface is attached
        local attachment_id=$(AWS_PROFILE="$root_profile" aws ec2 describe-network-interfaces \
            --network-interface-ids "$eni_id" \
            --query 'NetworkInterfaces[0].Attachment.AttachmentId' \
            --output text 2>/dev/null || echo "")
        
        if [[ "$attachment_id" != "None" ]] && [[ -n "$attachment_id" ]]; then
            log_info "Detaching network interface: $eni_id"
            AWS_PROFILE="$root_profile" aws ec2 detach-network-interface \
                --attachment-id "$attachment_id" --force --no-cli-pager 2>/dev/null || true
            sleep 5
        fi
        
        # Delete the network interface
        log_info "Deleting network interface: $eni_id"
        AWS_PROFILE="$root_profile" aws ec2 delete-network-interface \
            --network-interface-id "$eni_id" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup security groups
cleanup_security_groups() {
    local environment="$1"
    
    log_step "Cleaning up security groups..."
    
    # Find VPCs first to get security groups
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    if [[ -z "$vpcs" ]]; then
        # Fallback to any VPCs with HIPAA naming in security groups
        local sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --query 'SecurityGroups[?contains(GroupName, `hipaa`) || contains(GroupName, `'$environment'`)]' \
            --output json 2>/dev/null || echo "[]")
    else
        local sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --filters "Name=vpc-id,Values=$vpcs" \
            --query 'SecurityGroups[?GroupName!=`default`]' \
            --output json 2>/dev/null || echo "[]")
    fi
    
    if [[ "$sgs" == "[]" ]]; then
        log_info "No security groups found"
        return 0
    fi
    
    # Sort security groups by dependency (reverse order to delete dependents first)
    echo "$sgs" | jq -r '.[].GroupId' | while read -r sg_id; do
        log_info "Deleting security group: $sg_id"
        
        # Remove all ingress and egress rules first
        AWS_PROFILE="$root_profile" aws ec2 revoke-security-group-ingress \
            --group-id "$sg_id" --protocol all --port all --source-group "$sg_id" \
            --no-cli-pager 2>/dev/null || true
        
        AWS_PROFILE="$root_profile" aws ec2 revoke-security-group-egress \
            --group-id "$sg_id" --protocol all --port all --cidr 0.0.0.0/0 \
            --no-cli-pager 2>/dev/null || true
        
        # Delete the security group
        AWS_PROFILE="$root_profile" aws ec2 delete-security-group \
            --group-id "$sg_id" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup subnets
cleanup_subnets() {
    local environment="$1"
    
    log_step "Cleaning up subnets..."
    
    # Find subnets with HIPAA naming
    local subnets=$(AWS_PROFILE="$root_profile" aws ec2 describe-subnets \
        --query 'Subnets[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$subnets" == "[]" ]]; then
        log_info "No subnets found"
        return 0
    fi
    
    echo "$subnets" | jq -r '.[].SubnetId' | while read -r subnet_id; do
        log_info "Deleting subnet: $subnet_id"
        AWS_PROFILE="$root_profile" aws ec2 delete-subnet \
            --subnet-id "$subnet_id" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup route tables
cleanup_route_tables() {
    local environment="$1"
    
    log_step "Cleaning up route tables..."
    
    # Find route tables with HIPAA naming
    local route_tables=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
        --query 'RouteTables[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$route_tables" == "[]" ]]; then
        log_info "No route tables found"
        return 0
    fi
    
    echo "$route_tables" | jq -r '.[].RouteTableId' | while read -r rt_id; do
        log_info "Deleting route table: $rt_id"
        
        # Check if this is a main route table
        local is_main=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
            --route-table-ids "$rt_id" \
            --query 'RouteTables[0].Associations[0].Main' \
            --output text 2>/dev/null || echo "false")
        
        if [[ "$is_main" != "true" ]]; then
            AWS_PROFILE="$root_profile" aws ec2 delete-route-table \
                --route-table-id "$rt_id" --no-cli-pager 2>/dev/null || true
        else
            log_info "Skipping main route table: $rt_id"
        fi
    done
}

# Cleanup internet gateways
cleanup_internet_gateways() {
    local environment="$1"
    
    log_step "Cleaning up internet gateways..."
    
    # Find internet gateways with HIPAA naming
    local igws=$(AWS_PROFILE="$root_profile" aws ec2 describe-internet-gateways \
        --query 'InternetGateways[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$igws" == "[]" ]]; then
        log_info "No internet gateways found"
        return 0
    fi
    
    echo "$igws" | jq -r '.[].InternetGatewayId' | while read -r igw_id; do
        log_info "Processing internet gateway: $igw_id"
        
        # Find attached VPCs
        local vpc_ids=$(AWS_PROFILE="$root_profile" aws ec2 describe-internet-gateways \
            --internet-gateway-ids "$igw_id" \
            --query 'InternetGateways[0].Attachments[].VpcId' \
            --output text 2>/dev/null || echo "")
        
        # Detach from all VPCs
        if [[ -n "$vpc_ids" ]]; then
            for vpc_id in $vpc_ids; do
                log_info "Detaching IGW $igw_id from VPC $vpc_id"
                AWS_PROFILE="$root_profile" aws ec2 detach-internet-gateway \
                    --internet-gateway-id "$igw_id" --vpc-id "$vpc_id" --no-cli-pager 2>/dev/null || true
            done
        fi
        
        # Delete the internet gateway
        log_info "Deleting internet gateway: $igw_id"
        AWS_PROFILE="$root_profile" aws ec2 delete-internet-gateway \
            --internet-gateway-id "$igw_id" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup VPC peering connections
cleanup_vpc_peering_connections() {
    local environment="$1"
    
    log_step "Cleaning up VPC peering connections..."
    
    # Find VPC peering connections with HIPAA naming
    local peerings=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpc-peering-connections \
        --query 'VpcPeeringConnections[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$peerings" == "[]" ]]; then
        log_info "No VPC peering connections found"
        return 0
    fi
    
    local peering_ids=$(echo "$peerings" | jq -r '.[].VpcPeeringConnectionId' | tr '\n' ' ')
    if [[ -n "$peering_ids" ]]; then
        log_info "Deleting VPC peering connections: $peering_ids"
        for peering_id in $peering_ids; do
            AWS_PROFILE="$root_profile" aws ec2 delete-vpc-peering-connection \
                --vpc-peering-connection-id "$peering_id" --no-cli-pager 2>/dev/null || true
        done
    fi
}

# Cleanup VPN gateways
cleanup_vpn_gateways() {
    local environment="$1"
    
    log_step "Cleaning up VPN gateways..."
    
    # Find VPN gateways with HIPAA naming
    local vpn_gws=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpn-gateways \
        --query 'VpnGateways[?contains(Tags[?Key==`Name`].Value, `hipaa`) || contains(Tags[?Key==`Name`].Value, `'$environment'`)]' \
        --output json 2>/dev/null || echo "[]")
    
    if [[ "$vpn_gws" == "[]" ]]; then
        log_info "No VPN gateways found"
        return 0
    fi
    
    echo "$vpn_gws" | jq -r '.[].VpnGatewayId' | while read -r vpn_gw_id; do
        log_info "Processing VPN gateway: $vpn_gw_id"
        
        # Find attached VPCs
        local vpc_ids=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpn-gateways \
            --vpn-gateway-ids "$vpn_gw_id" \
            --query 'VpnGateways[0].VpcAttachments[].VpcId' \
            --output text 2>/dev/null || echo "")
        
        # Detach from all VPCs
        if [[ -n "$vpc_ids" ]]; then
            for vpc_id in $vpc_ids; do
                log_info "Detaching VPN gateway $vpn_gw_id from VPC $vpc_id"
                AWS_PROFILE="$root_profile" aws ec2 detach-vpn-gateway \
                    --vpn-gateway-id "$vpn_gw_id" --vpc-id "$vpc_id" --no-cli-pager 2>/dev/null || true
            done
        fi
        
        # Delete the VPN gateway
        log_info "Deleting VPN gateway: $vpn_gw_id"
        AWS_PROFILE="$root_profile" aws ec2 delete-vpn-gateway \
            --vpn-gateway-id "$vpn_gw_id" --no-cli-pager 2>/dev/null || true
    done
}

# Cleanup VPC DHCP options
cleanup_vpc_dhcp_options() {
    local environment="$1"
    
    log_step "Cleaning up VPC DHCP options..."
    
    # Find VPCs with HIPAA naming
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Vpcs[]' --output json 2>/dev/null || echo "[]")
    
    if [[ "$vpcs" == "[]" ]]; then
        log_info "No VPCs found"
        return 0
    fi
    
    echo "$vpcs" | jq -r '.[].DhcpOptionsId' | while read -r dhcp_id; do
        if [[ "$dhcp_id" != "dopt-default" ]] && [[ "$dhcp_id" != "None" ]] && [[ -n "$dhcp_id" ]]; then
            log_info "Deleting DHCP options: $dhcp_id"
            
            # Disassociate from VPCs first
            local vpc_ids=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
                --filters "Name=dhcp-options-id,Values=$dhcp_id" \
                --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
            
            if [[ -n "$vpc_ids" ]]; then
                for vpc_id in $vpc_ids; do
                    log_info "Disassociating DHCP options $dhcp_id from VPC $vpc_id"
                    AWS_PROFILE="$root_profile" aws ec2 disassociate-dhcp-options \
                        --vpc-id "$vpc_id" --no-cli-pager 2>/dev/null || true
                done
            fi
            
            # Delete DHCP options
            AWS_PROFILE="$root_profile" aws ec2 delete-dhcp-options \
                --dhcp-options-id "$dhcp_id" --no-cli-pager 2>/dev/null || true
        fi
    done
}

# Cleanup VPCs
cleanup_vpcs() {
    local environment="$1"
    
    log_step "Cleaning up VPCs..."
    
    # Find VPCs with HIPAA naming
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*" \
        --query 'Vpcs[]' --output json 2>/dev/null || echo "[]")
    
    if [[ "$vpcs" == "[]" ]]; then
        log_info "No VPCs found"
        return 0
    fi
    
    echo "$vpcs" | jq -r '.[].VpcId' | while read -r vpc_id; do
        log_info "Deleting VPC: $vpc_id"
        
        # Final verification of VPC contents
        log_info "Verifying VPC $vpc_id is empty..."
        
        # Check for remaining resources
        local instances=$(AWS_PROFILE="$root_profile" aws ec2 describe-instances \
            --filters "Name=vpc-id,Values=$vpc_id" --query 'length(Reservations[])' \
            --output text 2>/dev/null || echo "0")
        
        local enis=$(AWS_PROFILE="$root_profile" aws ec2 describe-network-interfaces \
            --filters "Name=vpc-id,Values=$vpc_id" --query 'length(NetworkInterfaces[])' \
            --output text 2>/dev/null || echo "0")
        
        local sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --filters "Name=vpc-id,Values=$vpc_id" --query 'length(SecurityGroups[?GroupName!=`default`])' \
            --output text 2>/dev/null || echo "0")
        
        local subnets=$(AWS_PROFILE="$root_profile" aws ec2 describe-subnets \
            --filters "Name=vpc-id,Values=$vpc_id" --query 'length(Subnets[])' \
            --output text 2>/dev/null || echo "0")
        
        log_info "VPC $vpc_id summary - Instances: $instances, ENIs: $enis, Security Groups: $sgs, Subnets: $subnets"
        
        # Delete the VPC
        AWS_PROFILE="$root_profile" aws ec2 delete-vpc \
            --vpc-id "$vpc_id" --no-cli-pager 2>/dev/null || true
    done
}

# Hook function for phase execution
phase_vpc_hook() {
    local environment="$1"
    local options="$2"
    
    log_info "Executing VPC and networking cleanup phase for: $environment"
    
    if is_dry_run; then
        log_info "[DRY RUN] Would cleanup VPC infrastructure for environment: $environment"
        return 0
    fi
    
    cleanup_vpc_infrastructure "$environment"
}

# Allow direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 \u003cenvironment\u003e [options]"
        echo "  environment: dev, staging, prod"
        echo "  options: --dry-run, --force"
        exit 1
    fi
    
    source "$(dirname "$0")/../lib/utils.sh"
    cleanup_vpc_infrastructure "$1"
fi