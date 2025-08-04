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
        --filters "Name=tag:Name,Values=*hipaa*,*pulumi*,*$environment*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    local sgs
    if [[ -z "$vpcs" ]]; then
        # Fallback to any security groups with relevant naming
        sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --query 'SecurityGroups[?contains(GroupName, `hipaa`) || contains(GroupName, `'$environment'`) || contains(GroupName, `pulumi`) || contains(GroupName, `ecs`) || contains(GroupName, `alb`) || contains(GroupName, `rds`)]' \
            --output json 2>/dev/null || echo "[]")
    else
        sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --filters "Name=vpc-id,Values=$vpcs" \
            --query 'SecurityGroups[?GroupName!=`default`]' \
            --output json 2>/dev/null || echo "[]")
    fi
    
    if [[ "$sgs" == "[]" ]]; then
        log_info "No security groups found"
        return 0
    fi
    
    # First pass: Remove all rules to resolve dependencies
    log_info "Removing security group rules to resolve dependencies..."
    echo "$sgs" | jq -r '.[].GroupId' | while read -r sg_id; do
        if [[ -n "$sg_id" ]]; then
            local sg_name=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
                --group-ids "$sg_id" --query 'SecurityGroups[0].GroupName' \
                --output text 2>/dev/null || echo "unknown")
            
            log_info "Removing rules from security group: $sg_name ($sg_id)"
            
            # Get current ingress rules
            local ingress_rules=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
                --group-ids "$sg_id" --query 'SecurityGroups[0].IpPermissions' \
                --output json 2>/dev/null || echo "[]")
            
            # Remove ingress rules
            if [[ "$ingress_rules" != "[]" ]] && [[ "$ingress_rules" != "null" ]]; then
                AWS_PROFILE="$root_profile" aws ec2 revoke-security-group-ingress \
                    --group-id "$sg_id" --ip-permissions "$ingress_rules" \
                    --no-cli-pager 2>/dev/null || true
            fi
            
            # Get current egress rules
            local egress_rules=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
                --group-ids "$sg_id" --query 'SecurityGroups[0].IpPermissionsEgress' \
                --output json 2>/dev/null || echo "[]")
            
            # Remove egress rules (keep only if it's not the default allow-all rule)
            if [[ "$egress_rules" != "[]" ]] && [[ "$egress_rules" != "null" ]]; then
                # Filter out the default 0.0.0.0/0 rule to avoid errors
                local filtered_egress=$(echo "$egress_rules" | jq '[.[] | select(.IpRanges | length == 0 or (.IpRanges[] | .CidrIp != "0.0.0.0/0"))]')
                if [[ "$filtered_egress" != "[]" ]] && [[ "$filtered_egress" != "null" ]]; then
                    AWS_PROFILE="$root_profile" aws ec2 revoke-security-group-egress \
                        --group-id "$sg_id" --ip-permissions "$filtered_egress" \
                        --no-cli-pager 2>/dev/null || true
                fi
            fi
        fi
    done
    
    # Wait a moment for AWS to process the rule changes
    log_info "Waiting for rule changes to propagate..."
    sleep 10
    
    # Second pass: Delete security groups
    log_info "Deleting security groups..."
    echo "$sgs" | jq -r '.[].GroupId' | while read -r sg_id; do
        if [[ -n "$sg_id" ]]; then
            local sg_name=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
                --group-ids "$sg_id" --query 'SecurityGroups[0].GroupName' \
                --output text 2>/dev/null || echo "unknown")
            
            log_info "Deleting security group: $sg_name ($sg_id)"
            
            # Delete the security group with retries
            local attempts=0
            local max_attempts=5
            while [[ $attempts -lt $max_attempts ]]; do
                if AWS_PROFILE="$root_profile" aws ec2 delete-security-group \
                    --group-id "$sg_id" --no-cli-pager 2>/dev/null; then
                    log_info "Successfully deleted security group: $sg_name"
                    break
                else
                    attempts=$((attempts + 1))
                    if [[ $attempts -lt $max_attempts ]]; then
                        log_info "Failed to delete security group $sg_name, retrying in 10 seconds... (attempt $attempts/$max_attempts)"
                        sleep 10
                    else
                        log_warning "Failed to delete security group $sg_name after $max_attempts attempts"
                    fi
                fi
            done
        fi
    done
    
    # Third pass: Verify cleanup and handle any remaining groups
    log_info "Verifying security group cleanup..."
    local remaining_sgs
    if [[ -n "$vpcs" ]]; then
        remaining_sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --filters "Name=vpc-id,Values=$vpcs" \
            --query 'SecurityGroups[?GroupName!=`default`]' \
            --output json 2>/dev/null || echo "[]")
    else
        remaining_sgs=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
            --query 'SecurityGroups[?contains(GroupName, `hipaa`) || contains(GroupName, `'$environment'`) || contains(GroupName, `pulumi`) || contains(GroupName, `ecs`) || contains(GroupName, `alb`) || contains(GroupName, `rds`)]' \
            --output json 2>/dev/null || echo "[]")
    fi
    
    if [[ "$remaining_sgs" != "[]" ]]; then
        local count=$(echo "$remaining_sgs" | jq length)
        log_warning "$count security groups could not be deleted, likely due to dependencies"
        echo "$remaining_sgs" | jq -r '.[].GroupId' | while read -r sg_id; do
            if [[ -n "$sg_id" ]]; then
                local sg_name=$(AWS_PROFILE="$root_profile" aws ec2 describe-security-groups \
                    --group-ids "$sg_id" --query 'SecurityGroups[0].GroupName' \
                    --output text 2>/dev/null || echo "unknown")
                log_warning "Remaining security group: $sg_name ($sg_id)"
            fi
        done
    else
        log_info "All security groups successfully cleaned up"
    fi
}

# Cleanup subnets
cleanup_subnets() {
    local environment="$1"
    
    log_step "Cleaning up subnets..."
    
    # Find subnets in HIPAA VPCs (get VPCs first, then their subnets)
    local hipaa_vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*,*HIPAA*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    local subnets="[]"
    if [[ -n "$hipaa_vpcs" ]]; then
        # Convert space-separated VPC IDs to comma-separated for AWS CLI
        local vpc_list=$(echo "$hipaa_vpcs" | tr ' ' ',')
        subnets=$(AWS_PROFILE="$root_profile" aws ec2 describe-subnets \
            --filters "Name=vpc-id,Values=$vpc_list" \
            --query 'Subnets[]' --output json 2>/dev/null || echo "[]")
    fi
    
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
    
    # Find route tables in HIPAA VPCs and any orphaned route tables with blackhole routes
    local hipaa_vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*,*HIPAA*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    # Also find VPCs by direct ID matching our known problem VPCs
    local known_vpcs="vpc-0d12efa2260d63acf vpc-0cb84f5b3af83f2bb"
    local all_vpcs="$hipaa_vpcs $known_vpcs"
    
    local route_tables="[]"
    if [[ -n "$all_vpcs" ]]; then
        # Remove duplicates and create comma-separated list
        local vpc_list=$(echo "$all_vpcs" | tr ' ' '\n' | sort -u | tr '\n' ',' | sed 's/,$//')
        route_tables=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
            --filters "Name=vpc-id,Values=$vpc_list" \
            --query 'RouteTables[]' --output json 2>/dev/null || echo "[]")
    fi
    
    if [[ "$route_tables" == "[]" ]]; then
        log_info "No route tables found"
        return 0
    fi
    
    # First pass: Remove problematic routes (blackhole routes to deleted IGWs)
    log_info "Removing problematic routes from route tables..."
    echo "$route_tables" | jq -r '.[].RouteTableId' | while read -r rt_id; do
        if [[ -z "$rt_id" ]]; then continue; fi
        
        log_info "Checking route table for problematic routes: $rt_id"
        
        # Get routes for this route table
        local routes=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
            --route-table-ids "$rt_id" \
            --query 'RouteTables[0].Routes[]' --output json 2>/dev/null || echo "[]")
        
        if [[ "$routes" != "[]" ]]; then
            # Look for blackhole routes or routes to non-existent gateways
            echo "$routes" | jq -c '.[]' | while IFS= read -r route; do
                local state=$(echo "$route" | jq -r '.State // "active"')
                local gateway_id=$(echo "$route" | jq -r '.GatewayId // "none"')
                local dest_cidr=$(echo "$route" | jq -r '.DestinationCidrBlock // "none"')
                
                if [[ "$state" == "blackhole" ]] || [[ "$gateway_id" =~ ^igw-.* ]]; then
                    log_info "Found problematic route in $rt_id: $dest_cidr -> $gateway_id (state: $state)"
                    
                    # Try to delete the problematic route
                    if [[ "$dest_cidr" != "none" ]] && [[ "$dest_cidr" != "local" ]]; then
                        log_info "Removing route $dest_cidr from route table $rt_id"
                        AWS_PROFILE="$root_profile" aws ec2 delete-route \
                            --route-table-id "$rt_id" \
                            --destination-cidr-block "$dest_cidr" \
                            --no-cli-pager 2>/dev/null || true
                    fi
                fi
            done
        fi
    done
    
    # Wait for route deletions to propagate
    log_info "Waiting for route deletions to propagate..."
    sleep 5
    
    # Second pass: Delete non-main route tables
    log_info "Deleting custom route tables..."
    echo "$route_tables" | jq -r '.[].RouteTableId' | while read -r rt_id; do
        if [[ -z "$rt_id" ]]; then continue; fi
        
        log_info "Processing route table: $rt_id"
        
        # Check if this is a main route table
        local associations=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
            --route-table-ids "$rt_id" \
            --query 'RouteTables[0].Associations[]' --output json 2>/dev/null || echo "[]")
        
        local is_main="false"
        if [[ "$associations" != "[]" ]]; then
            is_main=$(echo "$associations" | jq -r 'map(.Main) | any')
        fi
        
        if [[ "$is_main" != "true" ]]; then
            log_info "Deleting custom route table: $rt_id"
            
            # Disassociate any subnet associations first
            if [[ "$associations" != "[]" ]]; then
                echo "$associations" | jq -r '.[] | select(.SubnetId != null) | .RouteTableAssociationId' | while read -r assoc_id; do
                    if [[ -n "$assoc_id" ]] && [[ "$assoc_id" != "null" ]]; then
                        log_info "Disassociating route table $rt_id from subnet (association: $assoc_id)"
                        AWS_PROFILE="$root_profile" aws ec2 disassociate-route-table \
                            --association-id "$assoc_id" --no-cli-pager 2>/dev/null || true
                    fi
                done
            fi
            
            # Now delete the route table
            AWS_PROFILE="$root_profile" aws ec2 delete-route-table \
                --route-table-id "$rt_id" --no-cli-pager 2>/dev/null || true
        else
            log_info "Skipping main route table: $rt_id"
        fi
    done
    
    # Third pass: Verify cleanup
    log_info "Verifying route table cleanup..."
    local remaining_tables="[]"
    if [[ -n "$all_vpcs" ]]; then
        local vpc_list=$(echo "$all_vpcs" | tr ' ' '\n' | sort -u | tr '\n' ',' | sed 's/,$//')
        remaining_tables=$(AWS_PROFILE="$root_profile" aws ec2 describe-route-tables \
            --filters "Name=vpc-id,Values=$vpc_list" \
            --query 'RouteTables[? !Associations[0].Main]' --output json 2>/dev/null || echo "[]")
    fi
    
    if [[ "$remaining_tables" != "[]" ]]; then
        local count=$(echo "$remaining_tables" | jq length)
        log_warning "$count custom route tables could not be deleted"
        echo "$remaining_tables" | jq -r '.[].RouteTableId' | while read -r rt_id; do
            if [[ -n "$rt_id" ]]; then
                log_warning "Remaining route table: $rt_id"
            fi
        done
    else
        log_info "All custom route tables successfully cleaned up"
    fi
}

# Cleanup internet gateways
cleanup_internet_gateways() {
    local environment="$1"
    
    log_step "Cleaning up internet gateways..."
    
    # Find internet gateways attached to HIPAA VPCs
    local hipaa_vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*,*HIPAA*" \
        --query 'Vpcs[].VpcId' --output text 2>/dev/null || echo "")
    
    local igws="[]"
    if [[ -n "$hipaa_vpcs" ]]; then
        for vpc_id in $hipaa_vpcs; do
            local vpc_igws=$(AWS_PROFILE="$root_profile" aws ec2 describe-internet-gateways \
                --filters "Name=attachment.vpc-id,Values=$vpc_id" \
                --query 'InternetGateways[]' --output json 2>/dev/null || echo "[]")
            if [[ "$vpc_igws" != "[]" ]]; then
                if [[ "$igws" == "[]" ]]; then
                    igws="$vpc_igws"
                else
                    igws=$(echo "$igws $vpc_igws" | jq -s 'add')
                fi
            fi
        done
    fi
    
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
    
    # Find VPCs with HIPAA naming (case insensitive)
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*,*HIPAA*" \
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
    
    # Find VPCs with HIPAA naming (case insensitive)
    local vpcs=$(AWS_PROFILE="$root_profile" aws ec2 describe-vpcs \
        --filters "Name=tag:Name,Values=*hipaa*,*HIPAA*" \
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