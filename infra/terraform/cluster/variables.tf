variable "cluster_endpoint_public_access_cidrs" {
  description = "Public IPv4 CIDRs allowed to reach the EKS API; set this to your current public IP /32."
  type        = list(string)
}

variable "aws_region" {
  description = "AWS region for the demo."
  type        = string
  default     = "ap-northeast-2"
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "agent-sandbox-demo"
}

variable "cluster_version" {
  description = "Amazon EKS Kubernetes minor version."
  type        = string
  default     = "1.35"
}

variable "environment" {
  description = "Environment tag. Only demo may use fewer than three Availability Zones."
  type        = string
  default     = "demo"
}

variable "availability_zone_count" {
  description = "Number of Availability Zones. Defaults to three; two is allowed only for demo. Subnet CIDR groups reserve ten slots each."
  type        = number
  default     = 3

  validation {
    condition     = var.availability_zone_count >= 2 && var.availability_zone_count <= 10 && floor(var.availability_zone_count) == var.availability_zone_count
    error_message = "availability_zone_count must be an integer between 2 and 10."
  }
}

variable "project_name" {
  description = "Project tag prefix."
  type        = string
  default     = "agent-sandbox-on-eks"
}

variable "service_ipv4_cidr" {
  description = "Cluster service CIDR. Must not overlap with the VPC or connected networks."
  type        = string
  default     = "10.100.0.0/16"
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the demo VPC."
  type        = string
  default     = "10.40.0.0/16"
}

locals {
  availability_zones = slice(data.aws_availability_zones.available.names, 0, var.availability_zone_count)

  public_subnet_cidrs   = [for index in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 8, index)]
  system_subnet_cidrs   = [for index in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 8, index + 10)]
  sandbox_subnet_cidrs  = [for index in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 8, index + 20)]
  firewall_subnet_cidrs = [for index in range(var.availability_zone_count) : cidrsubnet(var.vpc_cidr, 8, index + 30)]

  az_index = { for index, zone in local.availability_zones : zone => index }

  firewall_endpoint_by_az = {
    for state in aws_networkfirewall_firewall.egress.firewall_status[0].sync_states :
    state.availability_zone => state.attachment[0].endpoint_id
  }

  nat_return_routes = {
    for route in flatten([
      for zone, index in local.az_index : [
        { key = "${zone}-system", zone = zone, cidr = local.system_subnet_cidrs[index] },
        { key = "${zone}-sandbox", zone = zone, cidr = local.sandbox_subnet_cidrs[index] },
      ]
    ]) : route.key => route
  }

  dns_allow_domains = [
    "amazonaws.com",
    "*.amazonaws.com",
    "example.com",
    "example.org",
    "github.com",
    "*.github.com",
    "githubusercontent.com",
    "*.githubusercontent.com",
    "registry.k8s.io",
    "*.registry.k8s.io",
    # registry.k8s.io redirects image pulls to regional artifact registries.
    "*.pkg.dev",
    "googlecode.l.googleusercontent.com",
    "ghcr.io",
    "*.ghcr.io",
    "quay.io",
    "*.quay.io",
    "public.ecr.aws",
    "*.public.ecr.aws",
    "docker.io",
    "*.docker.io",
  ]
}
