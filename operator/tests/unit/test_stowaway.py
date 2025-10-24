from gefyra.connection.stowaway.utils import parse_wg_output


def test_wg_output():
    wg_output = """
interface: wg0
  public key: bY+CWLteoQhw4gsjstTyt7xM4Vozlo1OvOQvnFSdK4iU=
  private key: (hidden)
  listening port: 51820

peer: eqBvqFkdKlR55/XVwp4o8mYnJN9Gnp0jAn0=
  preshared key: (hidden)
  endpoint: 10.132.0.12:33416
  allowed ips: 192.168.99.3/32, 172.22.0.0/16
  latest handshake: 24 seconds ago
  transfer: 1.24 MiB received, 1.18 MiB sent

peer: HPmogNhzB3bb9dgkseKFMJ6LF5Yyk=
  preshared key: (hidden)
  allowed ips: 192.168.99.2/32, 172.23.0.0/16

peer: c96fTK2yzW5B8Oae96gSY7gg39M+JhndvnI=
  preshared key: (hidden)
  allowed ips: 192.168.99.4/32, 172.21.0.0/16

peer: 0p9Jc6PbUzXUuJ0F/pM26gFXJh/3vSc=
  preshared key: (hidden)
  allowed ips: 192.168.99.5/32, 172.20.0.0/16

peer: +k2gMdmjoMJPwyMERR+tg783QChSL54QYCw=
  preshared key: (hidden)
  allowed ips: 192.168.99.6/32

peer: fc1N/s3c/jDsx+ACYfrC2WOUVs=
  preshared key: (hidden)
  allowed ips: 192.168.99.7/32
  persistent keepalive: 25 seconds
"""

    parsed_data = parse_wg_output(wg_output)
    assert parsed_data == {
        "interface": {
            "name": "wg0",
            "public_key": "bY+CWLteoQhw4gsjstTyt7xM4Vozlo1OvOQvnFSdK4iU=",
            "private_key": "(hidden)",
            "listening_port": 51820,
        },
        "peers": [
            {
                "public_key": "eqBvqFkdKlR55/XVwp4o8mYnJN9Gnp0jAn0=",
                "preshared_key": "(hidden)",
                "endpoint": {"host": "10.132.0.12", "port": 33416},
                "allowed_ips": ["192.168.99.3/32", "172.22.0.0/16"],
                "latest_handshake": {"value": 24, "unit": "seconds"},
                "transfer": {
                    "received": {"value": 1.24, "unit": "MiB"},
                    "sent": {"value": 1.18, "unit": "MiB"},
                },
            },
            {
                "public_key": "HPmogNhzB3bb9dgkseKFMJ6LF5Yyk=",
                "preshared_key": "(hidden)",
                "allowed_ips": ["192.168.99.2/32", "172.23.0.0/16"],
            },
            {
                "public_key": "c96fTK2yzW5B8Oae96gSY7gg39M+JhndvnI=",
                "preshared_key": "(hidden)",
                "allowed_ips": ["192.168.99.4/32", "172.21.0.0/16"],
            },
            {
                "public_key": "0p9Jc6PbUzXUuJ0F/pM26gFXJh/3vSc=",
                "preshared_key": "(hidden)",
                "allowed_ips": ["192.168.99.5/32", "172.20.0.0/16"],
            },
            {
                "public_key": "+k2gMdmjoMJPwyMERR+tg783QChSL54QYCw=",
                "preshared_key": "(hidden)",
                "allowed_ips": ["192.168.99.6/32"],
            },
            {
                "public_key": "fc1N/s3c/jDsx+ACYfrC2WOUVs=",
                "preshared_key": "(hidden)",
                "allowed_ips": ["192.168.99.7/32"],
                "persistent_keepalive": {"value": 25, "unit": "seconds"},
            },
        ],
    }
