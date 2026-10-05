# OpenBao declarative self-initialisation (the `initialize` stanza,
# https://openbao.org/docs/configuration/self-init/), loaded as a SECOND
# server config file next to the chart's (see kustomization.yaml).
#
# Runs ONCE, on empty storage, right after OpenBao initialised itself with the
# auto-unseal (seal "static" / "transit"): no recovery keys are created, and
# the root token these requests run with is revoked when they are done. On
# every later start the instance is already initialised and this is skipped.
#
# What it leaves behind: userpass at auth/userpass, policy `terraform`, user
# `terraform` -- and nothing else that can log in.
#
# If a request fails, the server exits and from then on REFUSES TO UNSEAL
# ("self-initialization failed: refusing to unseal"). The fix is a fresh
# start: delete the PVC (data-openbao-0) and the pod.

initialize "userpass" {
  request "enable-userpass" {
    operation = "update"
    path      = "sys/auth/userpass"
    data = {
      type        = "userpass"
      description = "self-init: the terraform user"
    }
  }
}

initialize "terraform-policy" {
  request "write-policy" {
    operation = "update"
    path      = "sys/policies/acl/terraform"
    data = {
      policy = <<EOP
# The PKI mount at pki/ itself (vault_mount): create, read back, change,
# unmount. Mounting needs no sudo.
path "sys/mounts/pki" {
  capabilities = ["create", "read", "update", "delete"]
}

# The mount's tunables (vault_mount reads and updates TTLs and the ACME
# passthrough/allowed response headers here).
path "sys/mounts/pki/tune" {
  capabilities = ["read", "update"]
}

# The mount table, read-only: `bao secrets list` and a look at what is
# mounted. hashicorp/vault 5.12 does not need it (apply, plan and destroy pass
# without); it reveals mount names and settings, no secrets.
path "sys/mounts" {
  capabilities = ["read"]
}

# Everything inside the mount: config/cluster, config/urls, config/acme,
# roles/*, issuers + issuer/*, intermediate/generate/internal,
# intermediate/set-signed, issue/* + sign/* (tests), acme/new-eab. No sudo:
# none of these needs it (the sudo-only sign-self-issued stays out).
path "pki/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# The provider reads its own token on login. The default policy grants this
# too; stated here so the policy does not depend on it.
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
EOP
    }
  }
}

initialize "terraform-user" {
  request "create-user" {
    operation = "update"
    path      = "auth/userpass/users/terraform"
    data = {
      # From the environment, never in this file: the chart renders the
      # server config into a ConfigMap, readable by anyone with `get`.
      # require_present: an ABSENT variable fails the self-init; an EMPTY one
      # is rejected by userpass ("invalid request"). Either way: loud.
      password = {
        eval_type       = "string"
        eval_source     = "env"
        env_var         = "OPENBAO_TERRAFORM_PASSWORD"
        require_present = true
      }
      token_policies = ["terraform"]
      token_ttl      = "1h"
      token_max_ttl  = "4h"
    }
  }
}
