from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest


@pytest.mark.parametrize("fail", [False, True])
def test_overlapping_execs_leave_rest_transport_unchanged(fail):
    import kubernetes as k8s
    from kubernetes.stream.stream import _websocket_request
    from gefyra.utils import exec_command_pod

    configuration = k8s.client.Configuration()
    configuration.host = "https://selected-cluster.invalid"
    configuration.api_key["authorization"] = "test-token"
    configuration.refresh_api_key_hook = lambda config: None
    started = [Event(), Event()]
    release = [Event(), Event()]
    clients = []

    def websocket_request(config, *args, **kwargs):
        index = int(kwargs["query_params"][0][1])
        assert config is configuration
        started[index].set()
        assert release[index].wait(5)
        if fail and index == 0:
            raise RuntimeError("exec failed")
        return "done"

    def exec_method(api, name, namespace, **kwargs):
        assert namespace == "ns"
        assert kwargs["container"] == "app"
        assert kwargs["command"] == ["wg"]
        assert api.api_client.default_headers["X-Test"] == "selected-header"
        assert api.api_client.cookie == "selected-cookie"
        clients.append(api.api_client)
        return api.api_client.request("GET", "/exec", query_params=[("index", name)])

    def stream(method, *args, **kwargs):
        return _websocket_request(websocket_request, None, method, *args, **kwargs)

    with k8s.client.ApiClient(configuration) as rest_client:
        rest_client.default_headers["X-Test"] = "selected-header"
        rest_client.cookie = "selected-cookie"
        rest_api = k8s.client.CoreV1Api(rest_client)
        with (
            patch.object(rest_client, "request", return_value="rest") as request,
            patch.object(
                k8s.client.CoreV1Api, "connect_get_namespaced_pod_exec", exec_method
            ),
            patch("kubernetes.stream.stream", side_effect=stream),
            patch.object(k8s.client.ApiClient, "close", autospec=True) as close,
        ):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(
                    exec_command_pod, rest_api, "0", "ns", "app", ["wg"]
                )
                second = None
                try:
                    assert started[0].wait(5)
                    second = pool.submit(
                        exec_command_pod, rest_api, "1", "ns", "app", ["wg"]
                    )
                    assert started[1].wait(5)
                    assert rest_client.request is request
                    assert rest_client.request("GET", "/configmaps") == "rest"
                    # Finish in the order that corrupts a shared client.
                    release[0].set()
                    if fail:
                        with pytest.raises(RuntimeError, match="exec failed"):
                            first.result(timeout=5)
                    else:
                        assert first.result(timeout=5) == "done"
                    assert rest_client.request is request
                finally:
                    release[0].set()
                    release[1].set()
                assert second.result(timeout=5) == "done"
            assert rest_client.request is request
            assert len({id(client) for client in clients}) == 2
            assert all(client is not rest_client for client in clients)
            assert {id(call.args[0]) for call in close.call_args_list} == {
                id(client) for client in clients
            }
