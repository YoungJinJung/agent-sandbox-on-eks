resource "aws_networkfirewall_rule_group" "sandbox_egress" {
  name     = "${var.cluster_name}-sandbox-egress"
  type     = "STATEFUL"
  capacity = 100

  rule_group {
    stateful_rule_options {
      rule_order = "STRICT_ORDER"
    }

    rule_variables {
      ip_sets {
        key = "SYSTEM_NETS"
        ip_set { definition = local.system_subnet_cidrs }
      }
      ip_sets {
        key = "SANDBOX_NETS"
        ip_set { definition = local.sandbox_subnet_cidrs }
      }
    }

    rules_source {
      rules_string = <<-EOT
        pass ip $SYSTEM_NETS any -> any any (msg:"trusted system egress"; sid:1000; rev:1;)
        pass tls $SANDBOX_NETS any -> any 443 (msg:"allow example.com"; tls.sni; content:"example.com"; startswith; endswith; nocase; sid:1100; rev:1;)
        drop tls $SANDBOX_NETS any -> any 443 (msg:"deny non-allowlisted sandbox HTTPS"; tls.sni; pcre:"/./"; sid:1199; rev:1;)
      EOT
    }
  }

  tags = { Name = "${var.cluster_name}-sandbox-egress" }
}

resource "aws_networkfirewall_firewall_policy" "egress" {
  name = "${var.cluster_name}-egress"

  firewall_policy {
    stateless_default_actions          = ["aws:forward_to_sfe"]
    stateless_fragment_default_actions = ["aws:forward_to_sfe"]
    stateful_default_actions           = ["aws:drop_established"]

    stateful_engine_options {
      rule_order = "STRICT_ORDER"
    }

    stateful_rule_group_reference {
      resource_arn = aws_networkfirewall_rule_group.sandbox_egress.arn
      priority     = 100
    }
  }
}

resource "aws_networkfirewall_firewall" "egress" {
  name                              = "${var.cluster_name}-egress"
  firewall_policy_arn               = aws_networkfirewall_firewall_policy.egress.arn
  vpc_id                            = module.vpc.vpc_id
  delete_protection                 = false
  firewall_policy_change_protection = false
  subnet_change_protection          = false

  dynamic "subnet_mapping" {
    for_each = module.vpc.intra_subnets
    content {
      subnet_id = subnet_mapping.value
    }
  }

  tags = { Name = "${var.cluster_name}-egress" }
}

resource "aws_cloudwatch_log_group" "network_firewall" {
  name              = "/aws/network-firewall/${var.cluster_name}"
  retention_in_days = 7
}

resource "aws_networkfirewall_logging_configuration" "egress" {
  firewall_arn = aws_networkfirewall_firewall.egress.arn

  logging_configuration {
    log_destination_config {
      log_type             = "FLOW"
      log_destination_type = "CloudWatchLogs"
      log_destination = {
        logGroup = aws_cloudwatch_log_group.network_firewall.name
      }
    }

    log_destination_config {
      log_type             = "ALERT"
      log_destination_type = "CloudWatchLogs"
      log_destination = {
        logGroup = aws_cloudwatch_log_group.network_firewall.name
      }
    }
  }
}

resource "aws_route53_resolver_firewall_domain_list" "allowlist" {
  name    = "${var.cluster_name}-dns-allowlist"
  domains = [for domain in local.dns_allow_domains : "${domain}."]
}

resource "aws_route53_resolver_firewall_domain_list" "default_deny" {
  name    = "${var.cluster_name}-dns-default-deny"
  domains = ["*."]
}

resource "aws_route53_resolver_firewall_rule_group" "egress" {
  name = "${var.cluster_name}-dns-firewall"
}

resource "aws_route53_resolver_firewall_rule" "allow" {
  name                    = "allow-approved-domains"
  firewall_domain_list_id = aws_route53_resolver_firewall_domain_list.allowlist.id
  firewall_rule_group_id  = aws_route53_resolver_firewall_rule_group.egress.id
  priority                = 100
  action                  = "ALLOW"
}

resource "aws_route53_resolver_firewall_rule" "deny_rest" {
  name                    = "deny-unlisted-domains"
  firewall_domain_list_id = aws_route53_resolver_firewall_domain_list.default_deny.id
  firewall_rule_group_id  = aws_route53_resolver_firewall_rule_group.egress.id
  priority                = 200
  action                  = "BLOCK"
  block_response          = "NXDOMAIN"
}

resource "aws_route53_resolver_firewall_rule_group_association" "vpc" {
  name                   = "${var.cluster_name}-dns-firewall"
  firewall_rule_group_id = aws_route53_resolver_firewall_rule_group.egress.id
  priority               = 101
  vpc_id                 = module.vpc.vpc_id
}

resource "aws_cloudwatch_log_group" "resolver" {
  name              = "/aws/route53resolver/${var.cluster_name}"
  retention_in_days = 7
}

resource "aws_iam_role" "resolver_logs" {
  name               = "${var.cluster_name}-resolver-query-logs"
  assume_role_policy = data.aws_iam_policy_document.resolver_logs_trust.json
}

resource "aws_iam_role_policy" "resolver_logs" {
  role   = aws_iam_role.resolver_logs.id
  policy = data.aws_iam_policy_document.resolver_logs_write.json
}

resource "aws_route53_resolver_query_log_config" "vpc" {
  name            = "${var.cluster_name}-resolver-query-logs"
  destination_arn = aws_cloudwatch_log_group.resolver.arn
}

resource "aws_route53_resolver_query_log_config_association" "vpc" {
  resolver_query_log_config_id = aws_route53_resolver_query_log_config.vpc.id
  resource_id                  = module.vpc.vpc_id
}
