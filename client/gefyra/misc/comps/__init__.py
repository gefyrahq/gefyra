from . import namespace  # noqa
from . import rbac
from . import webhook
from . import service
from . import deployment

COMPONENTS = [namespace, rbac, webhook, deployment, service]
