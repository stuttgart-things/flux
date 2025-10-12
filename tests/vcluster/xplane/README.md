

helm upgrade --install vcluster loft/vcluster --version 0.29.0 --create-namespace -n vlcuster --set controlPlane.statefulSet.persistence.volumeClaim.storageClass=nfs4-csi --set controlPlane.distro.k3s.enabled=true

ARTIFACTS_FILE_SERVER=http://192.168.56.117:7173
helm upgrade --install tinkerbell oci://ghcr.io/tinkerbell/charts/tinkerbell --version v0.21.0 --set "artifactsFileServer=$ARTIFACTS_FILE_SERVER"

helm upgrade --install flux-operator oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator --namespace flux-system --create-namespace --version 0.24.0


```bash
kubectl apply -f - <<EOF
apiVersion: kubernetes.crossplane.io/v1alpha1
kind: ProviderConfig
metadata:
  name: in-cluster
spec:
  credentials:
    source: InjectedIdentity
EOF

SA=$(kubectl -n crossplane-system get sa -o name | grep provider-kubernetes | sed -e 's|serviceaccount\/|crossplane-system:|g')
kubectl create clusterrolebinding provider-kubernetes-admin-binding --clusterrole cluster-admin --serviceaccount="${SA}"
```

```bash
# Step 1: Install the KCL Function
cat <<EOF | kubectl apply -f -
apiVersion: pkg.crossplane.io/v1beta1
kind: Function
metadata:
  name: function-kcl
spec:
  package: xpkg.upbound.io/crossplane-contrib/function-kcl:v0.11.5
EOF

# Step 2: Wait for the function to be installed and healthy
echo "Waiting for function-kcl to be installed..."
kubectl wait --for=condition=Healthy --timeout=300s function/function-kcl


# Step 3: Check the Function status
kubectl get function function-kcl

# Step 4: Check FunctionRevision status
kubectl get functionrevision

# Step 5: Verify the function pod is running
kubectl get pods -n crossplane-system | grep function-kcl
```

kubectl -n crossplane-system create secret generic demo-infra --from-file=demo-infra

kubectl apply -f - <<EOF
apiVersion: kubernetes.crossplane.io/v1alpha1
kind: ProviderConfig
metadata:
  name: demo-infra
spec:
  credentials:
    source: Secret
    secretRef:
      namespace: crossplane-system
      name: demo-infra
      key: demo-infra
EOF