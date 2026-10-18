resource "aws_iam_role" "fargate_execution" {
  name = "${var.cluster_name}-fargate-execution"

  assume_role_policy = data.aws_iam_policy_document.fargate_trust.json
}

resource "aws_iam_role_policy_attachment" "fargate_execution" {
  role       = aws_iam_role.fargate_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy"
}

resource "aws_iam_role_policy" "fargate_logging" {
  role   = aws_iam_role.fargate_execution.id
  policy = data.aws_iam_policy_document.fargate_logging_write.json
}

resource "aws_iam_role" "sandbox" {
  name               = "${var.cluster_name}-sandbox"
  assume_role_policy = data.aws_iam_policy_document.sandbox_trust.json
}

# Deliberately attach no S3 policy: GetCallerIdentity works without an allow,
# while ListBuckets must produce AccessDenied in the live demonstration.
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "20.37.2"

  cluster_name              = var.cluster_name
  cluster_version           = var.cluster_version
  cluster_service_ipv4_cidr = var.service_ipv4_cidr

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = concat(module.vpc.private_subnets, module.vpc.database_subnets)
  control_plane_subnet_ids = module.vpc.private_subnets

  cluster_endpoint_private_access          = true
  cluster_endpoint_public_access           = true
  cluster_endpoint_public_access_cidrs     = var.cluster_endpoint_public_access_cidrs
  authentication_mode                      = "API"
  enable_irsa                              = true
  enable_cluster_creator_admin_permissions = true

  cluster_security_group_additional_rules = {
    sandbox_api = {
      description              = "Fargate sandbox access to the EKS API"
      protocol                 = "tcp"
      from_port                = 443
      to_port                  = 443
      type                     = "ingress"
      source_security_group_id = aws_security_group.sandbox.id
    }
    router_api = {
      description              = "Fargate router access to the EKS API"
      protocol                 = "tcp"
      from_port                = 443
      to_port                  = 443
      type                     = "ingress"
      source_security_group_id = aws_security_group.router.id
    }
    sandbox_dns_udp = {
      description              = "CoreDNS queries from sandbox pods"
      protocol                 = "udp"
      from_port                = 53
      to_port                  = 53
      type                     = "ingress"
      source_security_group_id = aws_security_group.sandbox.id
    }
    sandbox_dns_tcp = {
      description              = "CoreDNS TCP queries from sandbox pods"
      protocol                 = "tcp"
      from_port                = 53
      to_port                  = 53
      type                     = "ingress"
      source_security_group_id = aws_security_group.sandbox.id
    }
    router_dns_udp = {
      description              = "CoreDNS queries from router pods"
      protocol                 = "udp"
      from_port                = 53
      to_port                  = 53
      type                     = "ingress"
      source_security_group_id = aws_security_group.router.id
    }
    router_dns_tcp = {
      description              = "CoreDNS TCP queries from router pods"
      protocol                 = "tcp"
      from_port                = 53
      to_port                  = 53
      type                     = "ingress"
      source_security_group_id = aws_security_group.router.id
    }
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_eks_fargate_profile" "kube_system" {
  cluster_name           = module.eks.cluster_name
  fargate_profile_name   = "kube-system"
  pod_execution_role_arn = aws_iam_role.fargate_execution.arn
  subnet_ids             = module.vpc.private_subnets
  selector {
    namespace = "kube-system"
    labels    = { "k8s-app" = "kube-dns" }
  }

  depends_on = [
    aws_iam_role_policy_attachment.fargate_execution,
    aws_iam_role_policy.fargate_logging,
  ]
}

resource "aws_eks_fargate_profile" "argocd" {
  cluster_name           = module.eks.cluster_name
  fargate_profile_name   = "argocd"
  pod_execution_role_arn = aws_iam_role.fargate_execution.arn
  subnet_ids             = module.vpc.private_subnets
  selector { namespace = "argocd" }

  depends_on = [
    aws_iam_role_policy_attachment.fargate_execution,
    aws_iam_role_policy.fargate_logging,
  ]
}

resource "aws_eks_fargate_profile" "agent_sandbox_system" {
  cluster_name           = module.eks.cluster_name
  fargate_profile_name   = "agent-sandbox-system"
  pod_execution_role_arn = aws_iam_role.fargate_execution.arn
  subnet_ids             = module.vpc.private_subnets
  selector { namespace = "agent-sandbox-system" }

  depends_on = [
    aws_iam_role_policy_attachment.fargate_execution,
    aws_iam_role_policy.fargate_logging,
  ]
}

resource "aws_eks_fargate_profile" "sandbox_demo" {
  cluster_name           = module.eks.cluster_name
  fargate_profile_name   = "sandbox-demo"
  pod_execution_role_arn = aws_iam_role.fargate_execution.arn
  subnet_ids             = module.vpc.database_subnets
  selector { namespace = "sandbox-demo" }

  depends_on = [
    aws_iam_role_policy_attachment.fargate_execution,
    aws_iam_role_policy.fargate_logging,
  ]
}

resource "aws_eks_addon" "coredns" {
  cluster_name                = module.eks.cluster_name
  addon_name                  = "coredns"
  addon_version               = data.aws_eks_addon_version.coredns.version
  configuration_values        = jsonencode({ computeType = "Fargate" })
  resolve_conflicts_on_create = "OVERWRITE"
  resolve_conflicts_on_update = "OVERWRITE"

  depends_on = [aws_eks_fargate_profile.kube_system]
}

resource "aws_iam_role_policy_attachment" "vpc_resource_controller" {
  role       = module.eks.cluster_iam_role_name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
}

resource "aws_security_group_rule" "sandbox_from_router" {
  description              = "MCP requests from the sandbox router"
  type                     = "ingress"
  security_group_id        = aws_security_group.sandbox.id
  source_security_group_id = aws_security_group.router.id
  protocol                 = "tcp"
  from_port                = 8000
  to_port                  = 8000
}

resource "aws_security_group_rule" "sandbox_from_control_plane" {
  description              = "EKS kubelet management traffic to Fargate sandbox pods"
  type                     = "ingress"
  security_group_id        = aws_security_group.sandbox.id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  protocol                 = "tcp"
  from_port                = 10250
  to_port                  = 10250
}

resource "aws_security_group_rule" "sandbox_probe_from_control_plane" {
  description              = "Kubelet startup and liveness probes to the MCP port"
  type                     = "ingress"
  security_group_id        = aws_security_group.sandbox.id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  protocol                 = "tcp"
  from_port                = 8000
  to_port                  = 8000
}

resource "aws_security_group_rule" "router_from_control_plane" {
  description              = "EKS API-server tunnel for kubectl port-forward"
  type                     = "ingress"
  security_group_id        = aws_security_group.router.id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  protocol                 = "tcp"
  from_port                = 8080
  to_port                  = 8080
}

resource "aws_security_group_rule" "router_probe_from_control_plane" {
  description              = "Kubelet health probes to the sandbox router"
  type                     = "ingress"
  security_group_id        = aws_security_group.router.id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  protocol                 = "tcp"
  from_port                = 8081
  to_port                  = 8081
}

resource "aws_ecr_repository" "mcp_server" {
  name                 = "${var.cluster_name}/mcp-tools"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "mcp_server" {
  repository = aws_ecr_repository.mcp_server.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the most recent 10 demo images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
