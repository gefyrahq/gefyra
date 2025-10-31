from pprint import pprint
from kubernetes.config import load_kube_config
from kubernetes import client

# needs kubeconfig set!


def duplicate_deployment(connection_name: str, deployment_name: str, namespace: str):
    # Get the original deployment
    load_kube_config()
    api = client.AppsV1Api()
    deployment = api.read_namespaced_deployment(deployment_name, namespace)

    # Create a copy of the deployment
    new_deployment = deployment

    # Update labels to add -gefyra suffix
    labels = new_deployment.metadata.labels or {}
    for key in labels:
        labels[key] = f"{labels[key]}-gefyra"
    new_deployment.metadata.labels = labels
    new_deployment.metadata.resource_version = None
    new_deployment.metadata.uid = None
    new_deployment.metadata.name = f"{deployment_name}-gefyra"

    pod_labels = new_deployment.spec.template.metadata.labels or {}
    for key in pod_labels:
        pod_labels[key] = f"{pod_labels[key]}-gefyra"
    new_deployment.spec.template.metadata.labels = pod_labels

    match_labels = new_deployment.spec.selector.match_labels or {}
    for key in match_labels:
        match_labels[key] = f"{match_labels[key]}-gefyra"
    new_deployment.spec.selector.match_labels = match_labels

    # Create the new deployment
    api.create_namespaced_deployment(namespace, new_deployment)


def duplicate_service(connection_name: str, service_name: str, namespace: str):
    # Get the original service
    load_kube_config()
    api = client.CoreV1Api()
    service = api.read_namespaced_service(service_name, namespace)

    # Create a copy of the service
    new_service = service
    pprint(new_service)

    # Clean up the new_service object
    new_service.metadata.resource_version = None
    new_service.metadata.uid = None
    new_service.metadata.self_link = None
    new_service.metadata.creation_timestamp = None
    new_service.metadata.generation = None
    new_service.metadata.name = f"{service_name}-gefyra"
    new_service.spec.cluster_ip = None
    new_service.spec.cluster_i_ps = None

    # Update labels to add -gefyra suffix
    labels = new_service.metadata.labels or {}
    for key in labels:
        labels[key] = f"{labels[key]}-gefyra"
    new_service.metadata.labels = labels

    # Update selector labels
    pod_labels = new_service.spec.selector or {}
    for key in pod_labels:
        pod_labels[key] = f"{pod_labels[key]}-gefyra"
    new_service.spec.selector = pod_labels

    pprint(new_service)
    # Create the new service
    api.create_namespaced_service(namespace, new_service)
