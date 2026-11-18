terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.94" }
    helm = { source = "hashicorp/helm", version = "~> 2.17" }
    http = { source = "hashicorp/http", version = "~> 3.4" }
  }
}

# Keep AWS infrastructure and Kubernetes lifecycles separate: destroy this root first.
data "terraform_remote_state" "cluster" {
  backend = "local"
  config  = { path = "${path.module}/../cluster/terraform.tfstate" }
}

locals {
  cluster = data.terraform_remote_state.cluster.outputs
  app_values = {
    clusterName            = local.cluster.cluster_name
    awsRegion              = local.cluster.aws_region
    image                  = { repository = local.cluster.mcp_image_repository, tag = "demo" }
    sandboxRoleArn         = local.cluster.sandbox_role_arn
    sandboxSecurityGroupId = local.cluster.sandbox_security_group_id
    routerSecurityGroupId  = local.cluster.router_security_group_id
  }
}

provider "aws" {
  region = local.cluster.aws_region
}

data "aws_eks_cluster" "current" {
  name = local.cluster.cluster_name
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.current.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.current.certificate_authority[0].data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", local.cluster.cluster_name, "--region", local.cluster.aws_region]
    }
  }
}

data "http" "platform" {
  url = "https://github.com/kubernetes-sigs/agent-sandbox/releases/download/v1.0.5/sandbox-with-extensions.yaml"
}

resource "helm_release" "platform" {
  name             = "agent-sandbox-platform"
  namespace        = "agent-sandbox-system"
  create_namespace = false
  chart            = "${path.module}/platform-chart"
  timeout          = 600
  atomic           = true
  # Helm creates the namespace; all other pinned upstream resources remain intact.
  values = [yamlencode({
    manifest = trimprefix(data.http.platform.response_body, "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: agent-sandbox-system\n---\n")
  })]
  lifecycle {
    precondition {
      condition     = sha256(data.http.platform.response_body) == "b150cb058c577c59c42b060ff7f22e31b5311ca80430db98129f1280a0e85970"
      error_message = "The pinned Agent Sandbox v1.0.5 manifest changed. Review the upstream release before updating its checksum."
    }
  }
  depends_on = [helm_release.access]
}

# SecurityGroupPolicy must exist BEFORE Fargate Pod admission. Helm's default
# kind ordering does not guarantee that within a single release.
resource "helm_release" "access" {
  name             = "mcp-sandbox-access"
  namespace        = "agent-sandbox-system"
  create_namespace = true
  chart            = "${path.module}/../../../gitops/apps/mcp-sandbox"
  timeout          = 600
  atomic           = true
  values           = [yamlencode(merge(local.app_values, { installAccess = true, installWorkload = false, createSandboxNamespace = true }))]
}

resource "helm_release" "workload" {
  name       = "mcp-sandbox-workload"
  namespace  = "sandbox-demo"
  chart      = "${path.module}/../../../gitops/apps/mcp-sandbox"
  timeout    = 600
  atomic     = true
  values     = [yamlencode(merge(local.app_values, { installAccess = false, installWorkload = true }))]
  depends_on = [helm_release.platform]
}
