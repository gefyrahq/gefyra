import requests

assert (
    requests.post(
        "https://gefyra-admission.gefyra.svc/client-parameters", timeout=2, verify=False
    ).status_code
    == 400
)
