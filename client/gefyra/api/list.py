import logging
from typing import List

from gefyra.configuration import default_configuration

from .utils import stopwatch


logger = logging.getLogger(__name__)


@stopwatch
def list_interceptrequests(config=default_configuration) -> List[str]:
    from gefyra.local.bridge import get_all_interceptrequests

    ireqs = []
    for ireq in get_all_interceptrequests(config):
        ireqs.append(ireq["metadata"]["name"])
    return ireqs
