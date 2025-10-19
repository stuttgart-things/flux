import crossplane_provider_kubernetes.v1alpha2.kubernetes_crossplane_io_v1alpha2_object as obj

# Get the XR spec fields
name = option("params")?.oxr?.spec.name or ""
targetNamespace = option("params")?.oxr?.spec.targetNamespace or ""
templateRef = option("params")?.oxr?.spec.templateRef or ""
hardwareRef = option("params")?.oxr?.spec.hardwareRef or ""
macAddr = option("params")?.oxr?.spec.macAddr or ""

cluster = option("params")?.oxr?.spec.cluster or ""

# Boolean flag to control output - check explicitly for False
_printItemsValue = option("params")?.oxr?.spec.printItems
printItems = False if _printItemsValue == False else True

workflow_object = obj.Object {
    apiVersion = "kubernetes.crossplane.io/v1alpha2"
    kind = "Object"
    metadata = {
        name = name
    }
    spec = {
        forProvider = {
            manifest = {
                apiVersion = "tinkerbell.org/v1alpha1"
                kind = "Workflow"
                metadata = {
                    name = name
                    namespace = targetNamespace
                }
                spec = {
                    templateRef = templateRef
                    hardwareRef = hardwareRef
                    hardwareMap = {
                        device_1 = macAddr
                    }
                }
            }
        }
        deletionPolicy = "Delete"
        managementPolicies = ["*"]
        providerConfigRef = {
            name = cluster
        }
    }
}

items = [workflow_object] if printItems else []