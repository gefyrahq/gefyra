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
open("/tmp/health.log", "wa").write(res.text)
open("/tmp/health.log", "wa").write(res.status_code)
assert res.status_code == 200
