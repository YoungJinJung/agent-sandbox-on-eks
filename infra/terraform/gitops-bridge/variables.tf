variable "gitops_repository" {
  description = "Public Git repository URL containing the gitops/ directory."
  type        = string
}

variable "mcp_image_repository" {
  description = "ECR repository URI output by the cluster Terraform root."
  type        = string
}

variable "router_security_group_id" {
  description = "Router pod security group ID from the cluster Terraform root."
  type        = string
}

variable "sandbox_role_arn" {
  description = "Sandbox IRSA role ARN from the cluster Terraform root."
  type        = string
}

variable "sandbox_security_group_id" {
  description = "Sandbox pod security group ID from the cluster Terraform root."
  type        = string
}

variable "argocd_chart_version" {
  description = "Pinned Argo CD Helm chart version."
  type        = string
  default     = "10.10.2"
}

variable "argocd_url" {
  description = "Browser-reachable HTTPS base URL of Argo CD, used for GitHub OAuth callbacks. Leave empty to disable GitHub SSO."
  type        = string
  default     = ""

  validation {
    condition = (
      var.argocd_url == "" && var.github_organization == "" && var.github_oauth_client_id == ""
      ) || (
      startswith(var.argocd_url, "https://") && var.github_organization != "" && var.github_oauth_client_id != ""
    )
    error_message = "Set argocd_url (HTTPS), github_organization, and github_oauth_client_id together, or leave all three empty to disable GitHub SSO."
  }
}

variable "github_organization" {
  description = "GitHub organization whose members may sign in to Argo CD. Leave empty to disable GitHub SSO."
  type        = string
  default     = ""
}

variable "github_oauth_client_id" {
  description = "Client ID of the GitHub OAuth App used for Argo CD SSO. The client secret is supplied separately in a Kubernetes Secret."
  type        = string
  default     = ""
}

variable "github_admin_team" {
  description = "Optional GitHub team slug granted Argo CD admin access."
  type        = string
  default     = ""
}

variable "github_viewer_team" {
  description = "Optional GitHub team slug granted read-only Argo CD access."
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "Region where the EKS cluster was created."
  type        = string
  default     = "ap-northeast-2"
}

variable "cluster_name" {
  description = "Name of the existing EKS cluster."
  type        = string
  default     = "agent-sandbox-demo"
}

variable "image_tag" {
  description = "Tag pushed to the ECR repository before syncing the app."
  type        = string
  default     = "demo"
}
