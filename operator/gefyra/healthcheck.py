import os
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

mode = "a" if os.path.exists("/tmp/health.log") else "w"

content = f"{res.text} | {str(res.status_code)}\n"

open("/tmp/health.log", mode).write(content)
assert res.status_code == 200
