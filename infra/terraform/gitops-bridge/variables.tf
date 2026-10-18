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
