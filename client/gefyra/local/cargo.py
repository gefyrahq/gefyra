import logging
import ipaddress
from typing import Optional
from gefyra.configuration import ClientConfiguration
from gefyra.exceptions import GefyraConnectionError
from gefyra.types import StowawayConfig

logger = logging.getLogger("gefyra.cargo")


def get_cargo_ip_from_netaddress(network_address: str) -> str:
    return ".".join(network_address.split(".")[:3]) + ".149"


def probe_wireguard_connection(config: ClientConfiguration):
    from docker.models.containers import Container

    cargo: Container = config.DOCKER.containers.get(f"{config.CARGO_CONTAINER_NAME}")
    for _attempt in range(0, config.CARGO_PROBE_TIMEOUT * 2):
        logger.debug(
            f"Probing connection to {config.STOWAWAY_IP} (attempt {_attempt}/{config.CARGO_PROBE_TIMEOUT * 2}))"
        )
        _r = cargo.exec_run(f"timeout 1 ping -c 1 {config.STOWAWAY_IP}")
        if _r.exit_code != 0:
            continue
        else:
            break
    else:
        raise GefyraConnectionError(
            "Gefyra could not successfully confirm the connection working."
        )


def create_wireguard_config(
    params: StowawayConfig,
    cargo_endpoint: str,
    mtu: str = "1340",
    allowed_ips: str = "0.0.0.0/0",
    pre_up_script: Optional[str] = None,
) -> str:
    return (
        "[Interface]\n"
        f"Address = {params.iaddress}\n"
        f"MTU = {mtu}\n"
        f"PrivateKey = {params.iprivatekey}\n"
        f"DNS = {params.idns}\n"
        f"{'PreUp = ' + pre_up_script if pre_up_script else ''}\n"
        "PreUp = sysctl -w net.ipv4.ip_forward=1\n"
        "PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth1 -j MASQUERADE\n"  # noqa E501
        "PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth1 -j MASQUERADE\n"  # noqa E501
        "[Peer]\n"
        f"PublicKey = {params.ppublickey}\n"
        f"Endpoint = {cargo_endpoint}\n"
        f"PresharedKey = {params.presharedkey}\n"
        "PersistentKeepalive = 21\n"
        f"AllowedIPs = {allowed_ips}\n"
    )


# The following AllowdIPs calc code is from: https://github.com/ZerGo0/WireGuard-Allowed-IPs-Excluder
# TODO
# sorted_nets = sort_networks(exclude_networks(parse_ip_networks("0.0.0.0/0")[0], parse_ip_networks("78.47.20.215")[0]))
# allowed_ips = ",".join(map(str, sorted_nets))
def parse_ip_networks(ip_list_str):
    ip_list = ip_list_str.split(",")
    networks = []
    invalid_ip_addresses = []  # List to store invalid IPs.

    for ip in ip_list:
        ip = ip.strip()
        try:
            if "/" in ip:
                networks.append(ipaddress.ip_network(ip, strict=False))
            else:
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.version == 4:
                    networks.append(ipaddress.ip_network(f"{ip}/32", strict=False))
                else:
                    networks.append(ipaddress.ip_network(f"{ip}/128", strict=False))
        except ValueError:
            invalid_ip_addresses.append(ip)  # Add invalid IP to the list.

    return networks, invalid_ip_addresses  # Return both valid networks and invalid IPs.


def exclude_networks(allowed_networks, disallowed_networks):
    remaining_networks = set(allowed_networks)

    for disallowed in disallowed_networks:
        new_remaining_networks = set()

        for allowed in remaining_networks:
            if allowed.version == disallowed.version:
                if disallowed.subnet_of(allowed):
                    # If the disallowed network is a subnet of the allowed network, exclude it
                    new_remaining_networks.update(allowed.address_exclude(disallowed))
                elif allowed.overlaps(disallowed):
                    # Handle partial overlap
                    new_remaining_networks.update(
                        handle_partial_overlap(allowed, disallowed)
                    )
                else:
                    # If there's no overlap, keep the allowed network as it is.
                    new_remaining_networks.add(allowed)
            else:
                # If the IP versions don't match, keep the allowed network as it is.
                new_remaining_networks.add(allowed)

        # Update the remaining networks after processing each disallowed network
        remaining_networks = new_remaining_networks

    return remaining_networks


def handle_partial_overlap(allowed, disallowed):
    # This function will handle the case of a partial overlap and return the
    # non-overlapping portions of the allowed network.
    non_overlapping_networks = []

    # Calculate the IPs for the allowed and disallowed networks
    allowed_ips = list(allowed.hosts())
    disallowed_ips = set(disallowed.hosts())  # Use a set for faster lookup

    # Filter out the disallowed IPs
    allowed_ips = [ip for ip in allowed_ips if ip not in disallowed_ips]

    if not allowed_ips:
        # If no IPs are left, there's nothing to add
        return non_overlapping_networks

    # Create new network(s) from the remaining IPs.
    # This is a simplistic way and works on individual IPs, not ranges.
    # You might need a more efficient way to handle ranges of IPs, especially for large networks.
    for ip in allowed_ips:
        if ip.version == 4:
            non_overlapping_networks.append(
                ipaddress.ip_network(f"{ip}/32", strict=False)
            )
        else:
            non_overlapping_networks.append(
                ipaddress.ip_network(f"{ip}/128", strict=False)
            )

    return non_overlapping_networks


def sort_networks(networks):
    """Sort IP networks with all IPv4 first, then IPv6, each from lowest to highest."""
    ipv4 = []
    ipv6 = []
    for net in networks:
        if net.version == 4:
            ipv4.append(net)
        else:
            ipv6.append(net)
    # Sort each list individually
    ipv4_sorted = sorted(ipv4, key=lambda ip: ip.network_address)
    ipv6_sorted = sorted(ipv6, key=lambda ip: ip.network_address)

    # Combine the lists with all IPv4 addresses first, then IPv6
    return ipv4_sorted + ipv6_sorted
