# flake8: noqa
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions


def data(params: "GefyraInstallOptions") -> list[dict]:
    return [
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "gefyra-admission", "namespace": params.namespace},
            "spec": {
                "selector": {
                    "gefyra.dev/app": "gefyra-operator",
                    "gefyra.dev/role": "webhook",
                },
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
                        "caBundle": "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUZJekNDQXd1Z0F3SUJBZ0lVVUpxcE1PSkdH\nalU1Y21TZkN4NFlpcW1RLzk0d0RRWUpLb1pJaHZjTkFRRUwKQlFBd0pqRWtNQ0lHQTFVRUF3d2Ja\nMlZtZVhKaExXRmtiV2x6YzJsdmJpNW5aV1o1Y21FdWMzWmpNQjRYRFRJegpNRFV6TVRBNE1qTXdO\nbG9YRFRNek1EVXlPREE0TWpNd05sb3dKakVrTUNJR0ExVUVBd3diWjJWbWVYSmhMV0ZrCmJXbHpj\nMmx2Ymk1blpXWjVjbUV1YzNaak1JSUNJakFOQmdrcWhraUc5dzBCQVFFRkFBT0NBZzhBTUlJQ0Nn\nS0MKQWdFQWcwcFpoN2ZjaG42cStWay8ySnFwb0hQQlBJMGpxVTVSSjl5bUJ1Mm52T0pUVmVGekEz\nZGkzK1QxcVJvQQpGSnBUM2drd3B4aDFFNGtvZ256a1ZVejRoc3lPWnhJMnEwb0VYTEtpbktxdGQz\nbzd4ZXkvek5FK3FjQllLeEkvCjdIcWppVXh4cUMyNkdmZnY5amRzVUtXOU93OEl4NDJJc2VHZUVo\nMTlLeUZRaVREYmZoRFRPNVh4NHM2WFFnZVUKSCt2bFdwNFNldHczelhmbzlDd2hWTVVJZklKQWRs\nM3lBejhlY1VZZDN5WGtPSWFxWWpHVHNhS3Eyd2FOemZibwovMGlDalRjbElhenlIemNkcEFQNVlU\nOVBRVis0SUlpNGs4ZXB3dVVIUEtyZ2FlRDc5WmZGLzBvbjNDR1NqV21rCnV3VS9vTGp0S0lCOWlV\nNVBERXRYTkc5YzluRWhwbkFaNUM3L01DU2hJN1lCbXh1dHFQSk9OU0FJdURROVFRS2IKaThWWUhL\nMi80bjczSmJ2UmVNM01jdzdnanBlelhlOGRWSXZDWFdONXp3bDlZS0RFb3lFQXpuSU1WMWNXOWdO\nRgpYVUxtbFNJdy9icGtWd2l2T2U5OXljSld0QWhMNWZ3U0VVeHA2N1IxU3ZTQmNnUlRIVG5MOWtn\nRSthU2l1dWc1CkpidGwxTHdvOTZ6OUpOVC9leUtVTGhQSTZwTEN5ZzM4aXJKSkszYnRjZjA3Umdm\nVzlBSnRWOU5qblJQNlFjNWMKUHB4Um5xMlBxaVNpcGwwRG9xOFhOUnovc282bFQxRlZvZkZWcURm\nVXQ1dkZ2bFJOdEpZc3MrcFFWZEZUWW9SSApCbUV1N09tSy8xSUkxS3dVYnV3TDZSTHhGT1p6NkFT\nV3FxdWJOTURiejRSUWFXVUNBd0VBQWFOSk1FY3dKZ1lEClZSMFJCQjh3SFlJYloyVm1lWEpoTFdG\na2JXbHpjMmx2Ymk1blpXWjVjbUV1YzNaak1CMEdBMVVkRGdRV0JCVDUKeVFMU0Jkbkc4SGJtN3lE\nT2hKajQySk1oNlRBTkJna3Foa2lHOXcwQkFRc0ZBQU9DQWdFQWFzTi9hRXFrenBYSQpqVzAwQStv\naGtSMUh6eXQ0K29NaUxRaDJUYlkwNWh3eTlNWUtCdjVGTHpaMVcwb3A4Rm5jMGszVi9PVUJKNGdy\nCmhVODVRdHRYN3A4Skx5b0tFM21hdWx5c3dRZTNKVk81WHFxY04xRUx0N1c5TTZTNTQ2L2lINFIx\nQTR6SG1ybXoKVjIySGcxa3J5VHA4TmlETFJmV1lhcWdZNDZ3My9RSUtNbFBxU1BTTEl2MTNuL0dC\naGtOd1BTK2lTNVA4ejNJawpXVTFiVFJhbmJmN1M4TmlnRUV4NFVtMDkya1hQMC8yb3JKYUVRamNV\neGMweW14bVNpZnA2T2Y0YndKNUhsbkpOCm9WV1ZKV0YwckJZeGxTYm0xUnpmRFk2Uzg5d294ZTI2\nZ25rdWFsc3F2d2YycVZKRU1hZnBNdVkwMzRkZEdsaTUKQ0Y4a3hUcXNBa1V6Q0ZXaWhSNm9NTllR\ndGVadEhFdmdLREJtYVZtS0VsTEUxSEovVFZmK0o2MkhBZkhiSkJwRgpIVXRLL2FtZTZRTEtEcngy\nZ05JNDhCM3VZNGhleWwzbVJyK0wvanVZamJxdks1Unl0bXY0OFlMTjVJVUpkTXhzCmFTMnlLeDI3\nWjU0T2V2bWpVUzhKK0JEYXhQcGF2djdLblpYYlNlTWFXZklFMWgxOFQyQ1RjWEk3UzdrSGlKeUUK\naHBrVUdraWdJQkd4UnhkSFgvUWxtV0ZVU0RZR3hWTDZab3NjbW1MeHl5YTJ2L21MbGlWb2N1UVBr\ndWMrQXFnVApqeU0vY1ovUk1vMHFZNDZOem1oTlJobTM3YW4vbjNYNEIzVzlkRjJWbWFpNWIzSHZx\nbGdlQ1g4K1gzSzlnYXQrCmQ0bzZnZlA0SW10ZStlMGVEOXNKdHRjTjcrQVg5b2s9Ci0tLS0tRU5E\nIENFUlRJRklDQVRFLS0tLS0K\n",
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
        },
    ]
