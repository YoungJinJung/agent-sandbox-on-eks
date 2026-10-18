# GitOps Bridge bootstrap

Apply this root only after `../cluster` has created the EKS cluster and the MCP image has been pushed to ECR. It installs Argo CD, registers the in-cluster destination as a labeled cluster Secret, and publishes non-secret AWS metadata as annotations. Argo CD's ApplicationSets consume those annotations to populate the Helm values and deploy the controller/router and MCP sandbox chart from Git.

1. Copy `terraform.tfvars.example` to `terraform.tfvars`, set the public Git URL, and copy the five values from `terraform -chdir=../cluster output`.
2. To enable GitHub SSO, set `argocd_url`, `github_organization`, and `github_oauth_client_id`. Register a GitHub OAuth App with callback `<argocd_url>/api/dex/callback`. The URL must be reachable by the user's browser over HTTPS; this Terraform root leaves the Argo CD Service as `ClusterIP` and does not create an ingress/load balancer, so provide an existing endpoint/tunnel appropriate for your environment.
3. Before Terraform installs Argo CD, create the namespace and a separate client-secret Secret. Keep the OAuth client secret in a secure local file (or retrieve it from your secret manager), then run:

   ```sh
   kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
   kubectl create secret generic argocd-github-sso -n argocd \
     --from-file=clientSecret=/secure/path/github-oauth-client-secret \
     --dry-run=client -o yaml | kubectl apply -f -
   kubectl label secret argocd-github-sso -n argocd app.kubernetes.io/part-of=argocd --overwrite
   ```

   The secret value is not passed through Terraform or committed to Git. The chart's Dex configuration reads it from this Secret. Team slugs are optional: `github_admin_team` maps to Argo CD admin, `github_viewer_team` maps to read-only, and other allowed organization members receive read-only access by default. If the three required SSO settings are unset, Dex remains disabled.
4. Run `terraform init`, `terraform fmt -check -recursive`, `terraform validate`, `terraform plan`, and `terraform apply`.
5. Wait for both generated Argo CD Applications to sync. The MCP chart retries while the platform Application installs the Agent Sandbox CRDs.

The bridge Secret contains only cluster and deployment metadata, not AWS credentials. The sandbox IRSA role is passed as a role ARN; EKS injects short-lived credentials at Pod startup. Git is the source of truth for Kubernetes resources; Terraform owns AWS infrastructure and the small Argo CD bridge bootstrap.

GitHub SSO uses Dex's GitHub OAuth connector; it is separate from Git repository credentials. The current GitOps repository is public, so Argo CD does not need a repository credential. For a private repository, configure a separate read-only GitHub App credential.
