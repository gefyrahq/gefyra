from typing import Optional, List, TYPE_CHECKING
from gefyra.misc.comps import COMPONENTS
from gefyra.misc.utils import str_presenter

if TYPE_CHECKING:
    from gefyra.types import GefyraInstallOptions


def synthesize_config_as_dict(
    options: "GefyraInstallOptions", components: Optional[List[str]] = []  # noqa: B006
) -> list[dict]:
    req_comps = []
    if components:
        _comp_names = []
        for comp in COMPONENTS:
            comp_name = comp.__name__.split(".")[-1]
            _comp_names.append(comp_name)
            if comp_name in components:
                req_comps = [comp]
        if not req_comps or len(req_comps) != len(components):
            raise RuntimeError(
                f"Component(s) {','.join(components)} not found. "
                f"Choices are: {','.join(_comp_names)}"
            )
    else:
        req_comps = COMPONENTS

    data = []
    # generate the raw data
    for comp in req_comps:
        data.extend(comp.data(options))
    return data


def synthesize_config_as_yaml(
    options: "GefyraInstallOptions", components: Optional[List[str]] = []  # noqa: B006
) -> str:
    import yaml

    yaml.add_representer(str, str_presenter)
    data = synthesize_config_as_dict(options, components)
    _docs = []
    for doc in data:
        _docs.append(yaml.dump(doc))
    yaml_doc = ""
    if len(_docs) > 1:
        for idx, c in enumerate(_docs):
            if idx == 0:
                yaml_doc = c
            else:
                yaml_doc += f"\n---\n{c}"
    else:
        yaml_doc = _docs[0]

    return yaml_doc
