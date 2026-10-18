locals {
  github_sso_enabled = var.argocd_url != "" && var.github_organization != "" && var.github_oauth_client_id != ""
}

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
    dex = {
      enabled = local.github_sso_enabled
    }
    notifications = { enabled = false }
    "redis-ha"    = { enabled = false }
    controller    = { replicas = 1 }
    server = {
      replicas = 1
      service  = { type = "ClusterIP" }
    }
    configs = {
      cm = local.github_sso_enabled ? {
        url = var.argocd_url
        "dex.config" = yamlencode({
          connectors = [{
            type = "github"
            id   = "github"
            name = "GitHub"
            config = {
              clientID     = var.github_oauth_client_id
              clientSecret = "$argocd-github-sso:clientSecret"
              orgs = [{
                name  = var.github_organization
                teams = compact([var.github_admin_team, var.github_viewer_team])
              }]
            }
          }]
        })
      } : {}
      rbac = {
        scopes           = "[groups]"
        "policy.default" = local.github_sso_enabled ? "role:readonly" : ""
        "policy.csv" = local.github_sso_enabled ? join("\n", compact([
          "p, role:readonly, applications, get, */*, allow",
          "p, role:readonly, projects, get, *, allow",
          "p, role:readonly, clusters, get, *, allow",
          "p, role:readonly, repositories, get, *, allow",
          "p, role:admin, *, *, *, allow",
          var.github_admin_team != "" ? "g, ${var.github_organization}:${var.github_admin_team}, role:admin" : "",
          var.github_viewer_team != "" ? "g, ${var.github_organization}:${var.github_viewer_team}, role:readonly" : ""
        ])) : ""
      }
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
