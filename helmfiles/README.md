# HELMFILES

## GENERAL USAGE

<details><summary>RENDER/APPLY</summary>

</details>

<details><summary>HELMFILE CACHE</summary>

```bash
# SET CACHE DIR AND EXECUTE HELMFILE OPERATION (WHICH IS PULLING)
export HELMFILE_CACHE_HOME=/tmp/helmfile
helmfile template -f nginx.yaml

# CHECK DOWNLOAD GIT REPO STRUCTURE
ls -lta /tmp/helmfile 

# DELETE CACHE FOR TRY 'N ERROR W/ GIT SOURCES
rm -rf /tmp/helmfile
```

</details>


## APPS

<details><summary>NGINX</summary>

```bash
cat <<EOF > nginx.yaml
---
helmfiles:
  - path: git::https://github.com/stuttgart-things/flux.git@helmfiles/nginx.yaml?ref=feature/add-keycloak
    values:
      - serviceType: ClusterIP
EOF

helmfile tempplate -f nginx.yaml
```

</details>


Author Information
------------------
Patrick Hermann, stuttgart-things 03/2023
