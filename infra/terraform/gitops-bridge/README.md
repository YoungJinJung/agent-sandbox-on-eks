# GitOps Bridge bootstrap

Apply this root only after `../cluster` has created the EKS cluster and the MCP image has been pushed to ECR. It installs Argo CD, registers the in-cluster destination as a labeled cluster Secret, and publishes non-secret AWS metadata as annotations. Argo CD's ApplicationSets consume those annotations to populate the Helm values and deploy the controller/router and MCP sandbox chart from Git.

1. Copy `terraform.tfvars.example` to `terraform.tfvars`.
2. Set the public Git URL and copy the five values from `terraform -chdir=../cluster output`.
3. Run `terraform init`, `terraform fmt -check -recursive`, `terraform validate`, `terraform plan`, and `terraform apply`.
4. Wait for both generated Argo CD Applications to sync. The MCP chart retries while the platform Application installs the Agent Sandbox CRDs.

The bridge Secret contains only cluster and deployment metadata, not AWS credentials. The sandbox IRSA role is passed as a role ARN; EKS injects short-lived credentials at Pod startup. Git is the source of truth for Kubernetes resources; Terraform owns AWS infrastructure and the small Argo CD bridge bootstrap.
