resource "helm_release" "argocd" {
  name             = "argocd"
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = var.argocd_chart_version
  namespace        = "argocd"
  create_namespace = true
  timeout          = 900
  wait             = true

  values = [yamlencode({
    dex           = { enabled = false }
    notifications = { enabled = false }
    "redis-ha"    = { enabled = false }
    controller    = { replicas = 1 }
    server = {
      replicas = 1
      service  = { type = "ClusterIP" }
    }
    repoServer     = { replicas = 1 }
    applicationSet = { replicas = 1 }
  })]
}

resource "helm_release" "gitops_bridge" {
  name       = "sandbox-gitops-bootstrap"
  chart      = "${path.module}/../../../gitops/bootstrap"
  namespace  = "argocd"
  timeout    = 300
  wait       = true
  depends_on = [helm_release.argocd]

  values = [yamlencode({
    cluster = {
      name                   = var.cluster_name
      caData                 = data.aws_eks_cluster.current.certificate_authority[0].data
      region                 = var.aws_region
      gitopsRepository       = var.gitops_repository
      sandboxImageRepository = var.mcp_image_repository
      sandboxImageTag        = var.image_tag
      sandboxRoleArn         = var.sandbox_role_arn
      sandboxSecurityGroupId = var.sandbox_security_group_id
      routerSecurityGroupId  = var.router_security_group_id
    }
  })]
}
