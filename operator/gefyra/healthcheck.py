import requests


res = requests.post(
    "https://gefyra-admission.gefyra.svc/client-parameters",
    json={
        "request": {
            "resource": {
                "group": "gefyra.dev",
                "version": "v1",
                "resource": "gefyraclients",
            },
            "userInfo": {},
            "object": {"check": True},
        },
    },
    timeout=2,
    verify=False,
)

assert res.status_code == 200
