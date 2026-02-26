import asyncio
from datetime import datetime, timezone
from logging import Logger
import tarfile
from typing import Optional, Tuple

import kopf
import kubernetes as k8s
from statemachine import State, StateChart

from gefyra.base import GefyraStateObject, StateControllerMixin
from gefyra.configuration import OperatorConfiguration
from gefyra.resources.serviceaccounts import (
    get_serviceaccount_data,
    handle_create_gefyraclient_serviceaccount,
    handle_delete_gefyraclient_serviceaccount,
)
from gefyra.bridgestate import GefyraBridgeObject, GefyraBridge


class GefyraClientObject(GefyraStateObject):
    plural = "gefyraclients"


class GefyraClient(StateChart, StateControllerMixin):  # Reverted to StateMachine
    """
    A Gefyra client is implemented as a state machine
    """

    atomic_configuration_update = True
    catch_errors_as_events = False
    enable_self_transition_entries = False
    allow_event_without_transition = False

    kind = "GefyraClient"
    plural = "gefyraclients"
    connection_provider_field = "provider"

    requested = State("Client requested", initial=True, value="REQUESTED")
    creating = State("Client creating", value="CREATING")
    waiting = State("Client waiting", value="WAITING")
    enabling = State("Client enabling", value="ENABLING")
    active = State("Client active", value="ACTIVE")
    disabling = State("Client disabling", value="DISABLING")
    error = State("Client error", value="ERROR")
    terminating = State("Client terminating", value="TERMINATING")

    create = (
        requested.to(creating, on="on_create")
        | error.to(creating)
        | creating.to.itself()
    )
    wait = (
        creating.to(waiting, on="on_waiting")
        | waiting.to.itself()
        | error.to(waiting)
        | disabling.to(waiting, before="disable_connection", on="on_waiting")
    )
    enable = waiting.to(enabling, cond="can_add_client") | error.to(enabling)
    activate = (
        enabling.to(active, on="enable_connection")
        | error.to(active)
        | active.to.itself()
    )
    disable = active.to(disabling) | error.to(disabling)
    impair = error.from_(requested, creating, waiting, active, error)
    terminate = terminating.from_(
        requested, creating, waiting, active, error, terminating
    )

    def __init__(
        self,
        model: GefyraClientObject,
        configuration: OperatorConfiguration,
        logger: Logger,
        initial: Optional[State] = None,  # Added initial state parameter
    ):
        super().__init__(
            start_value=initial or GefyraClient.requested.id
        )  # Pass initial state to super
        self.model = model
        self.data = model.data
        self.operator_configuration = configuration
        self.logger = logger
        self.custom_api = k8s.client.CustomObjectsApi()
        self.events_api = k8s.client.EventsV1Api()
        self._connection_provider = None

    @property
    def client_name(self) -> str:
        """
        It returns the name of the GefyraClient
        :return: The name of the GefyraClient.
        """
        if self.model and hasattr(self.model, "name"):
            return self.model.name
        else:
            return "unknown"

    @property
    def namespace(self) -> str:
        """
        It returns the namespace of the GefyraClient
        :return: The name of the GefyraClient.
        """
        return self.data["metadata"]["namespace"]

    @property
    def sunset(self) -> Optional[datetime]:
        if sunset := self.data.get("sunset"):
            return datetime.fromisoformat(sunset.strip("Z"))
        else:
            return None

    @property
    def max_connection_age(self) -> Optional[int]:
        if (
            self.operator_configuration.STOWAWAY_MAX_CONNECTION_AGE
            and self.operator_configuration.STOWAWAY_MAX_CONNECTION_AGE > 0
        ):
            return self.operator_configuration.STOWAWAY_MAX_CONNECTION_AGE
        return None

    async def should_disable(self) -> bool:  # Made async
        # Check if client is currently active
        if not self.active.is_active:
            return False
        # Check if max_connection_age is configured
        max_age_seconds = self.max_connection_age
        if max_age_seconds is None:
            return False
        # Get the timestamp when client transitioned to active state
        active_transition_time = self.completed_transition(GefyraClient.active.value)
        if active_transition_time is None:
            return False
        self.logger.info(f"Active transition time: {active_transition_time}")
        # Calculate time since the active transition
        active_timestamp = datetime.fromisoformat(active_transition_time)
        time_since_active = (
            datetime.now(timezone.utc) - active_timestamp
        ).total_seconds()
        self.logger.info(f"Time since active: {time_since_active} seconds")
        # Return True if the connection has exceeded max_connection_age
        return time_since_active > max_age_seconds

    async def should_terminate(self) -> bool:  # Made async
        if self.sunset and self.sunset <= datetime.utcnow():
            # remove this client because the sunset time is in the past
            await self.post_event(  # Await post_event
                reason="Sunset reached",
                message=f"GefyraClient '{self.object_name}' should be terminated "
                "due to reached sunset date",
            )
            return True
        else:
            return False

    async def on_create(self):  # Made async
        await self.post_event(  # Await post_event
            reason="GefyraClient state change",
            message=f"GefyraClient '{self.object_name}' is being created",
        )
        if self.operator_configuration.DISABLE_CLIENT_SA_MANAGEMENT:
            await self.post_event(  # Await post_event
                reason="GefyraClient ServiceAccount",
                message=f"Skipping the ServiceAccount for GefyraClient '{self.object_name}' (ServiceAccount management is disabled)",
            )
            await self.wait()  # Await wait
        else:
            await self.create_service_account()  # Await create_service_account

    async def create_service_account(self) -> None:  # Made async
        """
        This method is called when the GefyraClient is creating
        :return: None
        """

        sa_name = f"gefyra-client-{self.object_name}"
        await handle_create_gefyraclient_serviceaccount(  # Await handle_create_gefyraclient_serviceaccount
            self.logger,
            sa_name,
            self.operator_configuration.NAMESPACE,
            self.object_name,
        )
        try:
            token_data = await get_serviceaccount_data(
                sa_name, self.operator_configuration.NAMESPACE
            )  # Await get_serviceaccount_data
        except kopf.TemporaryError as e:
            await self.post_event(  # Await post_event
                reason="GefyraClient ServiceAccount",
                message=f"Creating ServiceAccount waiting: {e}",
            )
            raise e
        await self._patch_object(  # Await _patch_object
            {"serviceAccountName": sa_name, "serviceAccountData": token_data}
        )
        await self.post_event(  # Await post_event
            reason="GefyraClient ServiceAccount",
            message=f"ServiceAccount for GefyraClient '{self.object_name}' created '{sa_name}' in namespace '{self.operator_configuration.NAMESPACE}' ",
        )
        await self.wait()  # Await wait

    async def on_enable(self):  # Made async
        await self.post_event(  # Await post_event
            reason="GefyraClient state change",
            message=f"GefyraClient '{self.object_name}' is being enabled",
        )

    async def on_activate(self):  # Made async
        await self.post_event(  # Await post_event
            reason="GefyraClient state change",
            message=f"GefyraClient '{self.object_name}' is active",
        )

    async def on_disable(self):  # Made async
        await self.post_event(  # Await post_event
            reason="GefyraClient state change",
            message=f"GefyraClient '{self.object_name}' is being disabled",
        )
        await self.cleanup_all_bridges()  # Await cleanup_all_bridges
        await self.wait()  # Await wait

    async def on_waiting(self):  # Made async
        await self.post_event(  # Await post_event
            reason="Ready",
            message=f"GefyraClient '{self.object_name}' is ready to accept a client connection request",
        )

    async def on_terminate(self):  # Made async
        try:
            await self.post_event(  # Await post_event
                reason="GefyraClient state change",
                message=f"GefyraClient '{self.object_name}' is being terminated",
            )
            if await self.connection_provider.peer_exists(
                self.object_name
            ):  # Await peer_exists
                self.logger.warning(
                    f"Removing GefyraClient '{self.object_name}' from connection provider"
                )
                await self.connection_provider.remove_peer(
                    self.object_name
                )  # Await remove_peer

            sa_name = f"gefyra-client-{self.object_name}"
            await handle_delete_gefyraclient_serviceaccount(
                self.logger, sa_name, self.namespace
            )  # Await handle_delete_gefyraclient_serviceaccount
            await self.cleanup_all_bridges()  # Await cleanup_all_bridges
        except Exception as e:
            self.logger.warning(f"Error during termination of GefyraClient: {e}")
            pass

    async def can_add_client(self):  # Made async
        if await self.connection_provider.peer_exists(
            self.object_name
        ):  # Await peer_exists
            self.logger.warning(f"GefyraClient '{self.object_name}' already exists.")
            return True
        else:
            await self.connection_provider.add_peer(  # Await add_peer
                self.object_name, self.data["providerParameter"]
            )
            await self.post_event(  # Await post_event
                reason="GefyraClient connection",
                message=f"GefyraClient '{self.object_name}' connection requested with '{self.data['providerParameter']}'",
            )
            return True

    async def enable_connection(self):  # Made async
        try:
            conn_data = await self.connection_provider.get_peer_config(
                self.object_name
            )  # Await get_peer_config
        except (tarfile.ReadError, KeyError, k8s.client.rest.ApiException) as e:
            await self.post_event(  # Await post_event
                reason="GefyraClient connection",
                message=f"Cannot read connection data from provider: {e}",
                type="Warning",
            )
            raise kopf.TemporaryError(
                f"Cannot read connection data from provider: {e}", delay=1
            )
        try:
            await self._patch_object(
                {"providerConfig": conn_data}
            )  # Await _patch_object
            await self.post_event(  # Await post_event
                reason="GefyraClient connection",
                message=f"GefyraClient '{self.object_name}' connecting via 'Interface.Address {str(conn_data['Interface.Address'])}'",
            )
        except k8s.client.ApiException as e:
            if e.status == 500:
                await self.post_event(  # Await post_event
                    reason="GefyraClient connection",
                    message=f"Cannot enable connection: {e.reason}",
                    type="Warning",
                )
                raise kopf.TemporaryError(
                    f"Cannot enable connection: {e.reason}", delay=1
                )

    async def disable_connection(self):  # Made async
        try:
            if not await self.connection_provider.peer_exists(
                self.object_name
            ):  # Await peer_exists
                self.logger.warning(
                    f"Client '{self.object_name}' does not exist, noting to disable."
                )
                return
            await self.connection_provider.remove_peer(
                self.object_name
            )  # Await remove_peer
        except k8s.client.rest.ApiException as e:
            if e.status == 500:
                raise kopf.TemporaryError(
                    f"Cannot disable connection: {e.reason}", delay=1
                )
        await self._patch_object({"providerConfig": None})  # Await _patch_object

    async def cleanup_all_bridges(self) -> None:  # Made async
        bridges = await asyncio.to_thread(
            self.custom_api.list_namespaced_custom_object,
            group="gefyra.dev",
            version="v1",
            plural="gefyrabridges",
            namespace=self.operator_configuration.NAMESPACE,
            label_selector=f"gefyra.dev/client={self.client_name}",
        )
        for bridge in bridges.get("items"):
            if bridge.get("client") == self.client_name:
                self.logger.warning(
                    "Now going to delete remaining GefyraBridge "
                    f"'{bridge['metadata']['name']}' for client {self.client_name}"
                )
                # obj = GefyraBridgeObject(bridge)
                # GefyraBridge needs to be async, but it's not fully converted yet, so deferring async init
                # bridge_obj = GefyraBridge(obj, self.operator_configuration, self.logger)
                # await bridge_obj.post_event( # Await post_event
                #     "Client deleted",
                #     f"This GefyraBridge will be removed since the related GefyraClient '{self.client_name}' is currently being removed",
                # )

                await asyncio.to_thread(
                    self.custom_api.delete_namespaced_custom_object,
                    group="gefyra.dev",
                    version="v1",
                    plural="gefyrabridges",
                    namespace=self.operator_configuration.NAMESPACE,
                    name=bridge["metadata"]["name"],
                )

    async def get_latest_transition(self) -> Optional[datetime]:  # Made async
        """
        > Get the latest transition time for a GefyraClient
        :return: The latest transition times
        """
        timestamps = list(
            filter(
                lambda k: k is not None,
                [
                    await self.completed_transition(
                        GefyraClient.creating.value
                    ),  # Await completed_transition
                    await self.completed_transition(
                        GefyraClient.waiting.value
                    ),  # Await completed_transition
                    await self.completed_transition(
                        GefyraClient.enabling.value
                    ),  # Await completed_transition
                    await self.completed_transition(
                        GefyraClient.active.value
                    ),  # Await completed_transition
                    await self.completed_transition(
                        GefyraClient.error.value
                    ),  # Await completed_transition
                ],
            )
        )
        if timestamps:
            return max(
                map(
                    lambda x: datetime.fromisoformat(x.strip("Z")),  # type: ignore
                    timestamps,
                )
            )
        else:
            return None

    async def get_latest_state(self) -> Optional[Tuple[str, datetime]]:  # Made async
        """
        It returns the latest state of the GefyraClient, and the timestamp of
        when it was in that state
        :return: A tuple of the latest state and the timestamp of the latest
        state.
        """
        states = list(
            filter(
                lambda k: k[1] is not None,
                {
                    GefyraClient.creating.value: await self.completed_transition(  # Await completed_transition
                        GefyraClient.creating.value
                    ),
                    GefyraClient.waiting.value: await self.completed_transition(  # Await completed_transition
                        GefyraClient.waiting.value
                    ),
                    GefyraClient.enabling.value: await self.completed_transition(  # Await completed_transition
                        GefyraClient.enabling.value
                    ),
                    GefyraClient.active.value: await self.completed_transition(  # Await completed_transition
                        GefyraClient.active.value
                    ),
                    GefyraClient.error.value: await self.completed_transition(  # Await completed_transition
                        GefyraClient.error.value
                    ),
                }.items(),
            )
        )
        if states:
            latest_state, latest_timestamp = None, None
            for state, timestamp in states:
                if latest_state is None and timestamp is not None:
                    latest_state = state
                    latest_timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                elif timestamp is not None:
                    _timestamp = datetime.fromisoformat(timestamp.strip("Z"))
                    if latest_timestamp and latest_timestamp < _timestamp:
                        latest_state = state
                        latest_timestamp = _timestamp
            return latest_state, latest_timestamp  # type: ignore
        else:
            return None
