def test_stowaway_persistent_volume_claim_uses_volume_resources():
    from gefyra.configuration import OperatorConfiguration
    from gefyra.connection.stowaway.resources.statefulsets import (
        create_stowaway_statefulset,
    )

    statefulset = create_stowaway_statefulset(
        labels={"app": "gefyra-stowaway"}, configuration=OperatorConfiguration()
    )

    resources = statefulset.spec.volume_claim_templates[0].spec.resources
    assert resources.requests == {"storage": "64Mi"}


def test_bridge_crd_array_items_are_a_schema_dictionary():
    from gefyra.resources.crds import create_gefyrabridge_definition

    definition = create_gefyrabridge_definition()

    port_mappings = definition.spec.versions[0].schema.open_apiv3_schema.properties[
        "portMappings"
    ]
    assert port_mappings.items == {"type": "string"}
