from utils import get_router_role, get_router_intent, get_id, format_interface, loopback_ip, ospf_router_id
from ip_plan import link_ips
from vrf import get_vrf_for_link


def generate_loopbacks(liste_routeurs, configs, intent):
    for r in liste_routeurs:
        if not get_router_intent(r, intent):
            continue
        lb_ip = loopback_ip(r, intent)
        configs[r] += f"interface Loopback0\n"
        configs[r] += f" ip address {lb_ip} 255.255.255.255\n"
        configs[r] += " no shutdown\n exit\n"


def generate_interfaces(gns3_data, nodes_map, configs, interfaces_actives, intent):
    for link in gns3_data['topology']['links']:
        node_a = link['nodes'][0]
        node_b = link['nodes'][1]
        name_a = nodes_map[node_a['node_id']]
        name_b = nodes_map[node_b['node_id']]

        if not get_router_intent(name_a, intent) or not get_router_intent(name_b, intent):
            continue

        ip_a, ip_b = link_ips(name_a, name_b, intent)
        int_a = format_interface(node_a['adapter_number'], node_a['port_number'])
        int_b = format_interface(node_b['adapter_number'], node_b['port_number'])

        role_a = get_router_role(name_a, intent)
        role_b = get_router_role(name_b, intent)

        vrf_a = None
        vrf_b = None
        if role_a == 'PE' and role_b == 'CE':
            vrf_a = get_vrf_for_link(name_a, name_b, intent)
        elif role_b == 'PE' and role_a == 'CE':
            vrf_b = get_vrf_for_link(name_b, name_a, intent)

        configs[name_a] += f"interface {int_a}\n"
        if vrf_a:
            configs[name_a] += f" vrf forwarding {vrf_a}\n"
        configs[name_a] += f" ip address {ip_a} 255.255.255.252\n no shutdown\n exit\n"

        configs[name_b] += f"interface {int_b}\n"
        if vrf_b:
            configs[name_b] += f" vrf forwarding {vrf_b}\n"
        configs[name_b] += f" ip address {ip_b} 255.255.255.252\n no shutdown\n exit\n"

        interfaces_actives[name_a].append(int_a)
        interfaces_actives[name_b].append(int_b)


def generate_ospf(liste_routeurs, gns3_data, nodes_map, configs, intent):
    for r in liste_routeurs:
        if not get_router_intent(r, intent):
            continue
        if get_router_role(r, intent) == 'CE':
            continue

        rid_str = ospf_router_id(r, intent)
        configs[r] += (f"router ospf 1\n"
                       f" router-id {rid_str}\n"
                       f" exit\n")
        configs[r] += "interface Loopback0\n ip ospf 1 area 0\n exit\n"

    for link in gns3_data['topology']['links']:
        node_a = link['nodes'][0]
        node_b = link['nodes'][1]
        name_a = nodes_map[node_a['node_id']]
        name_b = nodes_map[node_b['node_id']]

        data_a = get_router_intent(name_a, intent)
        data_b = get_router_intent(name_b, intent)

        if data_a and data_b and data_a['asn'] == data_b['asn']:
            int_a = format_interface(node_a['adapter_number'], node_a['port_number'])
            int_b = format_interface(node_b['adapter_number'], node_b['port_number'])
            for name, iface in [(name_a, int_a), (name_b, int_b)]:
                configs[name] += (f"interface {iface}\n"
                                  f" ip ospf 1 area 0\n"
                                  f" mpls ip\n"
                                  f"exit\n")


def generate_mpls(liste_routeurs, configs, intent):
    for r in liste_routeurs:
        if not get_router_intent(r, intent):
            continue
        if get_router_role(r, intent) not in ('P', 'PE'):
            continue

        rid = get_id(r)
        start_label = 100 + (rid - 1) * 200
        end_label = 100 + rid * 200 - 1
        configs[r] += f"mpls label range {start_label} {end_label}\n"
        configs[r] += "mpls label protocol ldp\n"


def generate_bgp(liste_routeurs, gns3_data, nodes_map, configs, intent):
    for r in liste_routeurs:
        data = get_router_intent(r, intent)
        if not data:
            continue

        role = get_router_role(r, intent)
        if role not in ('PE', 'CE'):
            continue

        asn = data['asn']
        bgp_rid = loopback_ip(r, intent)

        configs[r] += f"! --- BGP ---\n"
        configs[r] += f"router bgp {asn}\n"
        configs[r] += f" bgp log-neighbor-changes\n"
        configs[r] += f" no bgp default ipv4-unicast\n"
        configs[r] += f" bgp router-id {bgp_rid}\n"

        if role == 'PE':
            for other in data['routers']:
                if other == r:
                    continue
                if get_router_role(other, intent) == 'PE':
                    n_ip = loopback_ip(other, intent)
                    configs[r] += f" neighbor {n_ip} remote-as {asn}\n"
                    configs[r] += f" neighbor {n_ip} update-source Loopback0\n"

        for link in gns3_data['topology']['links']:
            name_a = nodes_map[link['nodes'][0]['node_id']]
            name_b = nodes_map[link['nodes'][1]['node_id']]
            neighbor_name = name_b if name_a == r else (name_a if name_b == r else None)
            if not neighbor_name:
                continue

            neighbor_data = get_router_intent(neighbor_name, intent)
            if not neighbor_data or neighbor_data['asn'] == asn:
                continue

            neighbor_role = get_router_role(neighbor_name, intent)
            if role == 'PE' and neighbor_role == 'CE':
                continue

            ip_me, ip_neighbor = link_ips(r, neighbor_name, intent)
            if name_b == r:
                ip_me, ip_neighbor = link_ips(neighbor_name, r, intent)
                ip_me, ip_neighbor = ip_neighbor, ip_me

            configs[r] += f" neighbor {ip_neighbor} remote-as {neighbor_data['asn']}\n"

        configs[r] += " address-family ipv4 unicast\n"
        if role == 'CE':
            lb_ip = loopback_ip(r, intent)
            configs[r] += f"  network {lb_ip} mask 255.255.255.255\n"

        as_prefix = data.get('prefix', '')
        if as_prefix:
            configs[r] += f"  network {as_prefix}.0.0 mask 255.255.0.0\n"

        if role == 'PE':
            for other in data['routers']:
                if other == r:
                    continue
                if get_router_role(other, intent) == 'PE':
                    n_ip = loopback_ip(other, intent)
                    configs[r] += f"  neighbor {n_ip} activate\n"

        for link in gns3_data['topology']['links']:
            name_a = nodes_map[link['nodes'][0]['node_id']]
            name_b = nodes_map[link['nodes'][1]['node_id']]
            neighbor_name = name_b if name_a == r else (name_a if name_b == r else None)
            if not neighbor_name:
                continue

            neighbor_data = get_router_intent(neighbor_name, intent)
            if not neighbor_data or neighbor_data['asn'] == asn:
                continue

            neighbor_role = get_router_role(neighbor_name, intent)
            if role == 'PE' and neighbor_role == 'CE' and get_vrf_for_link(r, neighbor_name, intent):
                continue

            ip_me, ip_neighbor = link_ips(r, neighbor_name, intent)
            if name_b == r:
                ip_me, ip_neighbor = link_ips(neighbor_name, r, intent)
                ip_me, ip_neighbor = ip_neighbor, ip_me

            configs[r] += f"  neighbor {ip_neighbor} activate\n"
            configs[r] += f"  neighbor {ip_neighbor} send-community\n"

        configs[r] += " exit-address-family\n"

        if role == 'PE':
            configs[r] += " address-family vpnv4\n"
            for other in data['routers']:
                if other == r:
                    continue
                if get_router_role(other, intent) == 'PE':
                    n_ip = loopback_ip(other, intent)
                    configs[r] += f"  neighbor {n_ip} activate\n"
                    configs[r] += f"  neighbor {n_ip} send-community both\n"
            configs[r] += " exit-address-family\n"

            pe_vrfs = {}
            for link in gns3_data['topology']['links']:
                name_a = nodes_map[link['nodes'][0]['node_id']]
                name_b = nodes_map[link['nodes'][1]['node_id']]
                ce_candidate = name_b if name_a == r else (name_a if name_b == r else None)
                if not ce_candidate:
                    continue
                if get_router_role(ce_candidate, intent) != 'CE':
                    continue

                vrf_name = get_vrf_for_link(r, ce_candidate, intent)
                if not vrf_name:
                    continue

                ip_me, ip_ce = link_ips(r, ce_candidate, intent)
                if name_b == r:
                    ip_me, ip_ce = link_ips(ce_candidate, r, intent)
                    ip_me, ip_ce = ip_ce, ip_me

                ce_asn = get_router_intent(ce_candidate, intent)['asn']
                pe_vrfs.setdefault(vrf_name, []).append((ip_ce, ce_asn, ip_me))

            for vrf_name, neighbors in pe_vrfs.items():
                configs[r] += f" address-family ipv4 vrf {vrf_name}\n"
                for ip_ce, ce_asn, ip_me in neighbors:
                    octets = ip_me.split(".")
                    last_octet = int(octets[3])
                    network_id = (last_octet // 4) * 4
                    subnet = f"{octets[0]}.{octets[1]}.{octets[2]}.{network_id}"
                    configs[r] += f"  network {subnet} mask 255.255.255.252\n"
                    configs[r] += f"  neighbor {ip_ce} remote-as {ce_asn}\n"
                    configs[r] += f"  neighbor {ip_ce} activate\n"
                configs[r] += " exit-address-family\n"

        configs[r] += " exit\n"


def generate_eem(liste_routeurs, configs, interfaces_actives):
    for r in liste_routeurs:
        if not interfaces_actives[r]:
            continue
        liste_int = ", ".join(interfaces_actives[r])
        configs[r] += f"""
!
! EEM Applet 1 — Activation retardée des interfaces (25s)
event manager applet GNS3_AUTO_NOSHUT
 event timer countdown time 25
 action 1.0 cli command "enable"
 action 2.0 cli command "configure terminal"
 action 3.0 cli command "interface range {liste_int}"
 action 4.0 cli command "no shutdown"
 action 5.0 cli command "end"
!
! EEM Applet 2 — Revalidation complète des interfaces (40s)
event manager applet GNS3_INTERFACE_REFRESH
 event timer countdown time 40
 action 1.0 cli command "enable"
 action 2.0 cli command "configure terminal"
 action 3.0 cli command "interface range {liste_int}"
 action 4.0 cli command "shutdown"
 action 5.0 cli command "no shutdown"
 action 6.0 cli command "end"
!
"""
