import requests


res = requests.post(
    "https://localhost:9443/client-parameters",
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
print(res.content)
assert res.status_code == 200
