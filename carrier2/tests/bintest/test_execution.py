from multiprocessing import Process, Queue


def test_a_execute_help(carrier2):
    res = carrier2("--help")
    assert "Command-line options" in res


def test_b_noargs(carrier2):
    res = carrier2("")
    assert "Idle mode" in res


def test_c_simple_config(carrier2):
    queue = Queue()
    # running carrier2 in a background process
    p = Process(target=carrier2, args=("-c ./config.yaml", 2, queue))
    p.start()
    p.join()
    res = queue.get(timeout=1)
    assert "probe ports: [Number(8001), Number(8002)]" in res
    assert "Server starting" in res
