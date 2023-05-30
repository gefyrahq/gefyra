# flake8: noqa
from gefyra.types import GefyraInstallOptions


def data(params: GefyraInstallOptions) -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "gefyra-admission", "namespace": params.namespace},
            "spec": {
                "selector": {"app": "gefyra-operator"},
                "ports": [{"protocol": "TCP", "port": 443, "targetPort": 9443}],
            },
        },
        {
            "apiVersion": "admissionregistration.k8s.io/v1",
            "kind": "ValidatingWebhookConfiguration",
            "metadata": {"name": "gefyra.dev"},
            "webhooks": [
                {
                    "admissionReviewVersions": ["v1", "v1beta1"],
                    "clientConfig": {
                        "caBundle": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUZDakNDQXZLZ0F3SUJBZ0lVTzJZMlJqUVdL\nVi9yTkJpOUx5Ry9xVWFqWENBd0RRWUpLb1pJaHZjTkFRRUwKQlFBd0tERW1NQ1FHQTFVRUF3d2RZ\nbVZwWW05dmRDMWhaRzFwYzNOcGIyNHVaMlYwWkdWamF5NXpkbU13SGhjTgpNakl4TVRFNE1qRXlO\nelUyV2hjTk1qTXhNVEU0TWpFeU56VTJXakFvTVNZd0pBWURWUVFEREIxaVpXbGliMjkwCkxXRmti\nV2x6YzJsdmJpNW5aWFJrWldOckxuTjJZekNDQWlJd0RRWUpLb1pJaHZjTkFRRUJCUUFEZ2dJUEFE\nQ0MKQWdvQ2dnSUJBTFd6OWc1dDdkbVN4dm9ob1hvSHRnQWsvdEpiOTlKLzNoekdzSGgwWExYbTBs\nbXJ3LzAvUjd4dworcXJPajdreUZ4R1NUREY0MGRmNyt5S3VTdkZxNGhpQjlqaFppakNTOFF4SFZ1\nTFVtMGNydjZGYWtKVmNVVW1DClZvRmkvNlJCVktLS0p4TzlRUU1YMWtaeUNXaW1wblN6d2Y0NDM5\nd0U0ZTJVcXBpWXl6Q2ZNZmlzQWVLRDE1dnQKYmRvM0NFYTVhc2tRTnFvZ0xYUWNxL0pkOTROYzN2\nQ2lVbGxUVXRJZkovb0VxS05tbmFqaHBRTVEwZ1plY0dESwo0SnZhcnNSd3I3N0RKUWllUWJsRi9w\naW0xcjQ2UGQzQk1DSHVMUVNrdERxdTNFK1BHZkNLZC95SmhKQVhUTmorClZqdGxUZGYxZm5MS0hM\nU1Qyck9MK3lzZVR1WnA4eGtEQnZNcmlCajg0RDVZeEVQNUIwZm9rVTM2UUZJMkdydFcKNjFPZjNN\nN1l4V3dFbHBhYUJnRFk5MDQvNU5TcE5WVFJBYVdZZHZDUmdnOC91Qmw2NXR1MGQ3d21jamlRK1Fm\nZQptRHhQczN0T29QMUZOcnYwUDk2dnRSVE55WGNVSXNUaWl4eDdQSjBkUnlINGdQdy92ZFluUElh\nRWFXOEpQaWI2CllVaVJHeFFWaXZLaDJ1NW1QaHlodzRxT3VNVHU5c1pIYjc4cEtpMGtsRko1TDNX\nWlNRUmFIUUZwRitVQncyclgKVDgzZjAxaDZXMlY3dm00TVNtRzBqcEYwdDM3cU1WUmNxVXpjeTFt\nUUVKVFFrck0rSVd1cGQ5V2d0cmhHc2M5RApvUXpGSTFIRm5mTGVMVXVUeVkrOVpNR25PcGlKVnNk\nMDNjMzJ0ay95SVcrbUZOTE8xbnJCQWdNQkFBR2pMREFxCk1DZ0dBMVVkRVFRaE1CK0NIV0psYVdK\ndmIzUXRZV1J0YVhOemFXOXVMbWRsZEdSbFkyc3VjM1pqTUEwR0NTcUcKU0liM0RRRUJDd1VBQTRJ\nQ0FRQ2JxQWJOT0hlUmdwbTloVmVSSDIxVHg1c2hmbEpzOU0vQy9iMDV2TUFWQjZiRgpBRktyNndT\nRDcwMk1yWFd4SG00SlZBY01xZVFvODlzb2J1S0FtUWd5WTdNdlllSnJHWjBrT0htZzRKZVcxTnFU\nCmhQUGRqNXdaZ05WcHg0dXl5NG9NK05pVW5CTndVS0diK2F0MGwxSmVLWUlwR1lySmtSQlo0ZmRk\nWlFvYU0yY1gKUmM1OWxCSisraVA2SnBuNGdKR2l2UEZwOGdTczFkanBUTWRWU3VJelJkbzlmNU81\nNEt6WnJ0di9ITzM5aVB6QQpSWnVNYlFzOU0zUDZObkQ0c3JSTjlQcG1KUXpuM1RSYlFUeDBoRkpw\nTmN0L1FkKzUyRzM1Tk81Zy9tVUk5aHowCjNRSy9rMlVSMUtMZ24ycURjMk4zanhjT1R2YURDbEVZ\nSDFnOVlMTnVuMU4rVzdLeUNwUzNlazhkZkgzeTRLNVQKZnUrT01VQjFRaDJJbWV3RzJTVnpFTmRE\nYjFxenMxellhYXlGVmFsalJEeW5MclJrTlUzWEo2WTlkMlM3NmllbApvZWtiT1N5RGtRdThHUllx\nQzNGckVROUN3STd5RFp1RnVoZnZGWTdrNzcvL3VuVDRHTDBOL0ZHa0JuZCtzUDFjCkxXbG9tVHB2\nY0NzM0JHbFNkVjVWQkJ1YjdDWk0zdkVBRkoyb1RjUXBEN1R1VFNlNE5PdUVMbkJYZG5HR0lUVUUK\nS044dWNQdGlZcDF1bDZwSGI3U0VWRVdSNVMvdkw4Q2pFcmFqS0ZTQWIySDExTUFmMU1CcEZvZm9v\nUkZJdFNyVQpFNVM2R0dybG15elluRG5OektVNG52b3BlUU1maVNQaHd4M3N2dnZJaEVFU3Z6aVVw\nV2QxcDVRNGlCUXFoZz09Ci0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K\n",
                        "service": {
                            "name": "gefyra-admission",
                            "namespace": params.namespace,
                            "path": "/client-parameters",
                        },
                    },
                    "failurePolicy": "Fail",
                    "matchPolicy": "Equivalent",
                    "name": "client-parameters.gefyra.dev",
                    "namespaceSelector": {},
                    "objectSelector": {},
                    "rules": [
                        {
                            "apiGroups": ["gefyra.dev"],
                            "apiVersions": ["v1"],
                            "operations": ["CREATE", "UPDATE"],
                            "resources": ["gefyraclients"],
                            "scope": "*",
                        }
                    ],
                    "sideEffects": "None",
                    "timeoutSeconds": 30,
                }
            ],
        }
    ]
