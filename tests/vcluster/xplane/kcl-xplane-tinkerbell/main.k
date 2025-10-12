import crossplane_provider_kubernetes.v1alpha2.kubernetes_crossplane_io_v1alpha2_object as obj

# Schema definition
schema WorkflowConfig:
    """
    Configuration schema for Tinkerbell Workflow

    Attributes:
        workflowName: Name of the workflow
        templateRef: Reference to the template to use
        hardwareRef: Reference to the hardware to use
        hardwareMap: Map of device identifiers to MAC addresses
        providerConfigRef: Reference to the Crossplane ProviderConfig
    """
    workflowName: str
    workflowNamespace: str = "default"  # Make optional with default
    templateRef: str
    hardwareRef: str
    hardwareMap: {str: str}
    providerConfigRef: str = "in-cluster"

# Configuration with variables that can be overridden with -D (not exported)
_config: WorkflowConfig = {
    workflowName = option("workflowName") or ""
    workflowNamespace = option("workflowNamespace") or "default"
    templateRef = option("templateRef") or ""
    hardwareRef = option("hardwareRef") or ""
    hardwareMap = option("hardwareMap") or {}
    providerConfigRef = option("providerConfigRef") or "in-cluster"
}

# Control variable to determine if workflow should be created (not exported)
_createWorkflow: bool = option("createWorkflow") or False

# Create a Kubernetes Object for Tinkerbell Workflow (conditionally)
if _createWorkflow:
    apiVersion = "kubernetes.crossplane.io/v1alpha2"
    kind = "Object"
    metadata = {
        name = _config.workflowName
        namespace = "default"
    }
    spec = {
        forProvider = {
            manifest = {
                apiVersion = "tinkerbell.org/v1alpha1"
                kind = "Workflow"
                metadata = {
                    name = _config.workflowName
                    namespace = _config.workflowNamespace
                }
                spec = {
                    templateRef = _config.templateRef
                    hardwareRef = _config.hardwareRef
                    hardwareMap = _config.hardwareMap
                }
            }
        }
        deletionPolicy = "Delete"
        managementPolicies = ["*"]

        # Reference to the ProviderConfig to use
        providerConfigRef = {
            name = _config.providerConfigRef
        }
    }