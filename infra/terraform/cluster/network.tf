module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.21.0"

  name = var.cluster_name
  cidr = var.vpc_cidr
  azs  = local.availability_zones

  public_subnets   = local.public_subnet_cidrs
  private_subnets  = local.system_subnet_cidrs
  database_subnets = local.sandbox_subnet_cidrs
  intra_subnets    = local.firewall_subnet_cidrs

  create_igw                       = true
  enable_nat_gateway               = false
  create_private_nat_gateway_route = false
  enable_dns_support               = true
  enable_dns_hostnames             = true
  map_public_ip_on_launch          = false

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
  database_subnet_tags = {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
    "Sandbox"                                   = "true"
  }
  intra_subnet_tags = {
    "NetworkFirewall" = "true"
  }
}

resource "aws_eip" "nat" {
  for_each = local.az_index
  domain   = "vpc"

  depends_on = [module.vpc]
}

resource "aws_nat_gateway" "egress" {
  for_each = local.az_index

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = module.vpc.public_subnets[each.value]

  depends_on = [module.vpc]
}

resource "aws_route" "firewall_to_nat" {
  for_each = local.az_index

  route_table_id         = module.vpc.intra_route_table_ids[each.value]
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.egress[each.key].id
}

resource "aws_route" "system_to_firewall" {
  for_each = local.az_index

  route_table_id         = module.vpc.private_route_table_ids[each.value]
  destination_cidr_block = "0.0.0.0/0"
  vpc_endpoint_id        = local.firewall_endpoint_by_az[each.key]
}

resource "aws_route" "sandbox_to_firewall" {
  for_each = local.az_index

  route_table_id         = module.vpc.database_route_table_ids[each.value]
  destination_cidr_block = "0.0.0.0/0"
  vpc_endpoint_id        = local.firewall_endpoint_by_az[each.key]
}

# NAT response packets must traverse the same AZ's stateful firewall endpoint.
resource "aws_route" "nat_return_to_firewall" {
  for_each = local.nat_return_routes

  route_table_id         = module.vpc.public_route_table_ids[local.az_index[each.value.zone]]
  destination_cidr_block = each.value.cidr
  vpc_endpoint_id        = local.firewall_endpoint_by_az[each.value.zone]
}

resource "aws_security_group" "sandbox" {
  name        = "${var.cluster_name}-sandbox"
  description = "Egress-limited MCP sandbox Fargate pods"
  vpc_id      = module.vpc.vpc_id

  egress {
    description = "DNS to CoreDNS service CIDR"
    protocol    = "udp"
    from_port   = 53
    to_port     = 53
    cidr_blocks = [var.service_ipv4_cidr]
  }

  egress {
    description = "DNS over TCP to CoreDNS service CIDR"
    protocol    = "tcp"
    from_port   = 53
    to_port     = 53
    cidr_blocks = [var.service_ipv4_cidr]
  }

  egress {
    description = "HTTPS; internet destinations are filtered by Network Firewall"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.cluster_name}-sandbox" }
}

resource "aws_security_group" "router" {
  name        = "${var.cluster_name}-sandbox-router"
  description = "Sandbox Router Fargate pods"
  vpc_id      = module.vpc.vpc_id

  egress {
    description = "DNS to CoreDNS service CIDR"
    protocol    = "udp"
    from_port   = 53
    to_port     = 53
    cidr_blocks = [var.service_ipv4_cidr]
  }

  egress {
    description = "DNS over TCP to CoreDNS service CIDR"
    protocol    = "tcp"
    from_port   = 53
    to_port     = 53
    cidr_blocks = [var.service_ipv4_cidr]
  }

  egress {
    description     = "Forward requests only to sandbox MCP pods"
    protocol        = "tcp"
    from_port       = 8000
    to_port         = 8000
    security_groups = [aws_security_group.sandbox.id]
  }

  tags = { Name = "${var.cluster_name}-sandbox-router" }
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "sts" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.sts"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "logs" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc.private_subnets
  security_group_ids  = [aws_security_group.endpoint.id]
  private_dns_enabled = true
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat(module.vpc.private_route_table_ids, module.vpc.database_route_table_ids)

  policy = data.aws_iam_policy_document.ecr_layer_access.json
}

resource "aws_security_group" "endpoint" {
  name        = "${var.cluster_name}-interface-endpoints"
  description = "HTTPS access to required AWS interface endpoints"
  vpc_id      = module.vpc.vpc_id

  ingress {
    description     = "HTTPS from MCP sandboxes"
    protocol        = "tcp"
    from_port       = 443
    to_port         = 443
    security_groups = [aws_security_group.sandbox.id]
  }

  ingress {
    description     = "HTTPS from the EKS cluster security group"
    protocol        = "tcp"
    from_port       = 443
    to_port         = 443
    security_groups = [module.eks.cluster_primary_security_group_id]
  }

  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.cluster_name}-interface-endpoints" }
}
