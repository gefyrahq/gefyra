from gefyra.misc.comps import COMPONENTS
from gefyra.misc.utils import str_presenter
from gefyra.types import GefyraInstallOptions


def synthesize_config_as_dict(
    options: GefyraInstallOptions, components: list[str] = []
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
                f"Component(s) {','.join(components)} not found. Choices are: {','.join(_comp_names)}"
            )
    else:
        req_comps = COMPONENTS

    data = []
    # generate the raw data
    for comp in req_comps:
        data.extend(comp.data(options))
    return data


def synthesize_config_as_json(
    options: GefyraInstallOptions, components: list[str] = []
) -> str:
    import json

    data = synthesize_config_as_dict(options, components)
    return json.dumps(data)


def synthesize_config_as_yaml(
    options: GefyraInstallOptions, components: list[str] = []
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
