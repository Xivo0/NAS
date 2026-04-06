import json
import os
import re

DOSSIER_PROJET = r"/Users/liamcorriveaud/GNS3/projects/test_config_gns"
FICHIER_GNS3 = os.path.join(DOSSIER_PROJET, "untitledv5.gns3")
FICHIER_INTENT = os.path.join(DOSSIER_PROJET, "intent.json")
DOSSIER_SORTIE = os.path.join(DOSSIER_PROJET, "configs_finales")


def get_id(nom_routeur):
    match = re.search(r'\d+', nom_routeur)
    return int(match.group()) if match else 0

def format_interface(adapter, port):
    if adapter == 0:
        return f"GigabitEthernet{adapter}/{port}"
    else:
        return f"FastEthernet{adapter}/{port}"


_subnet_counter_mpls  = -1
_subnet_counter_ce    = -1
_subnet_cache = {}
_subnet_counter_mpls_link = 0
_subnet_counter_ce_link = 0

def get_router_role(router_name, intent):
    for as_data in intent.get('as_list', []):
        if router_name in as_data.get('routers', []):
            role = as_data.get('role', '').upper()
            if role in ('P', 'PE', 'CE'):
                return role
    name_up = router_name.upper()
    if name_up.startswith('CE'):
        return 'CE'
    if name_up.startswith('PE'):
        return 'PE'
    if name_up.startswith('P'):
        return 'P'
    return 'P'


def get_router_intent(router_name):
    for as_data in intent.get('as_list', []):
        if router_name in as_data.get('routers', []):
            return as_data
    return None

def loopback_ip(router_name, intent):
    rid = get_id(router_name)
    role = get_router_role(router_name, intent)
    if role == 'P':
        if rid <= 255:
            return f"10.0.0.{rid}"
        else:
            return f"10.0.{rid - 255}.255"
    elif role == 'PE':
        if rid <= 255:
            return f"10.123.0.{rid}"
        elif rid <= 510:
            return f"10.123.{rid - 255}.255"
        else:
            return "plus assez de place"
    else:
        if rid <= 255:
            return f"10.255.0.{rid}"
        elif rid <= 510:
            return f"10.255.{rid - 255}.255"
        else:
            return "plus assez de place"


def ospf_router_id(router_name, intent):
    rid = get_id(router_name)
    role = get_router_role(router_name, intent)
    if role == 'P':
        if rid <= 255:
            return f"10.0.0.{rid}"
        elif rid <= 510:
            return f"10.0.{rid - 255}.255"
        else:
            return "plus assez de place"
    else:
        if rid <= 255:
            return f"1.0.0.{rid}"
        elif rid <= 510:
            return f"1.0.{rid - 255}.255"
        else:
            return "plus assez de place"


def get_link_subnet(name_a, name_b, role_a, role_b, intent):
    global _subnet_counter_mpls, _subnet_counter_ce, _subnet_counter_mpls_link, _subnet_counter_ce_link

    key = frozenset([name_a, name_b])
    if key in _subnet_cache:
        return _subnet_cache[key]

    mpls_roles = {'P', 'PE'}
    if role_a in mpls_roles and role_b in mpls_roles:
        if _subnet_counter_mpls_link == 0%64:
            _subnet_counter_mpls += 1
        n = _subnet_counter_mpls
        base = f"10.1.{n}"
        is_ce = False
    else:
        if _subnet_counter_ce_link == 0%64:
            _subnet_counter_ce += 1
        n = _subnet_counter_ce
        base = f"192.168.{n}"
        is_ce = True

    _subnet_cache[key] = (base, is_ce)
    return (base, is_ce)


def link_ips(name_a, name_b, intent):
    global _subnet_counter_mpls_link, _subnet_counter_ce_link

    rid_a = get_id(name_a)
    rid_b = get_id(name_b)
    role_a = get_router_role(name_a, intent)
    role_b = get_router_role(name_b, intent)
    base, _ = get_link_subnet(name_a, name_b, role_a, role_b, intent)

    if rid_a < rid_b:
        n_a = _subnet_counter_mpls_link + 1
        n_b = _subnet_counter_mpls_link + 2
        _subnet_counter_mpls_link = (_subnet_counter_mpls_link + 4) % 256
        return (f"{base}.{n_a}", f"{base}.{n_b}")
    else:
        n_a = _subnet_counter_ce_link + 2
        n_b = _subnet_counter_ce_link + 1
        _subnet_counter_ce_link = (_subnet_counter_ce_link + 4) % 256
        return (f"{base}.{n_a}", f"{base}.{n_b}")


def get_vrf_list(intent):
    return intent.get('vrf_list', [])


def get_vrf_for_link(pe_name, ce_name, intent):
    for assignment in intent.get('vrf_assignments', []):
        if assignment['pe'] == pe_name and assignment['ce'] == ce_name:
            return assignment['vrf']
    return None


def generate_vrf_config(intent):
    vrf_configs = {}
    vrf_list = get_vrf_list(intent)
    if not vrf_list:
        return vrf_configs

    for r in liste_routeurs:
        role = get_router_role(r, intent)
        if role != 'PE':
            continue

        pe_vrfs = set()
        for assignment in intent.get('vrf_assignments', []):
            if assignment['pe'] == r:
                pe_vrfs.add(assignment['vrf'])

        if not pe_vrfs:
            continue

        cfg = ""
        for vrf in vrf_list:
            if vrf['name'] not in pe_vrfs:
                continue
            cfg += f"vrf definition {vrf['name']}\n"
            cfg += f" rd {vrf['rd']}\n"
            cfg += f" route-target export {vrf['rt_export']}\n"
            cfg += f" route-target import {vrf['rt_import']}\n"
            cfg += f" !\n"
            cfg += f" address-family ipv4\n"
            cfg += f" exit-address-family\n"
            cfg += f"!\n"

        vrf_configs[r] = cfg

    return vrf_configs


if not os.path.exists(FICHIER_GNS3) or not os.path.exists(FICHIER_INTENT):
    print("ERREUR: Fichiers manquants (.gns3 ou intent.json)")
    exit()

with open(FICHIER_GNS3, 'r') as f:
    gns3_data = json.load(f)
with open(FICHIER_INTENT, 'r') as f:
    intent = json.load(f)

nodes_map = {node['node_id']: node['name'] for node in gns3_data['topology']['nodes']}
print(nodes_map)

liste_routeurs = sorted(list(nodes_map.values()), key=get_id)

configs = {r: f"! Config {r}\nip cef\n" for r in liste_routeurs}
interfaces_actives = {r: [] for r in liste_routeurs}


# -----------------------------------------------------------------------
print("0. Configuration des VRF...")
# -----------------------------------------------------------------------
vrf_configs = generate_vrf_config(intent)
for r, vrf_cfg in vrf_configs.items():
    configs[r] += vrf_cfg


# -----------------------------------------------------------------------
print("1. Configuration des IPs et Loopbacks (IPv4)...")
# -----------------------------------------------------------------------
for r in liste_routeurs:
    data = get_router_intent(r)
    if not data: continue

    lb_ip = loopback_ip(r, intent)
    configs[r] += f"interface Loopback0\n"
    configs[r] += f" ip address {lb_ip} 255.255.255.255\n"
    configs[r] += " no shutdown\n exit\n"


# -----------------------------------------------------------------------
# Liens physiques
# -----------------------------------------------------------------------
for link in gns3_data['topology']['links']:
    node_a = link['nodes'][0]
    node_b = link['nodes'][1]
    name_a = nodes_map[node_a['node_id']]
    name_b = nodes_map[node_b['node_id']]

    data_a = get_router_intent(name_a)
    data_b = get_router_intent(name_b)
    if not data_a or not data_b: continue

    ip_a, ip_b = link_ips(name_a, name_b, intent)
    int_a = format_interface(node_a['adapter_number'], node_a['port_number'])
    int_b = format_interface(node_b['adapter_number'], node_b['port_number'])

    # MODIFIÉ — détection du rôle pour vrf forwarding
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
    configs[name_a] += (f" ip address {ip_a} 255.255.255.252\n"
                        f" no shutdown\n exit\n")

    configs[name_b] += f"interface {int_b}\n"
    if vrf_b:
        configs[name_b] += f" vrf forwarding {vrf_b}\n"
    configs[name_b] += (f" ip address {ip_b} 255.255.255.252\n"
                        f" no shutdown\n exit\n")
    # FIN MODIFIÉ

    interfaces_actives[name_a].append(int_a)
    interfaces_actives[name_b].append(int_b)


# -----------------------------------------------------------------------
print("2. Configuration OSPF en IPv4...")
# -----------------------------------------------------------------------
for r in liste_routeurs:
    data = get_router_intent(r)
    if not data: continue

    proc = 1
    rid_str = ospf_router_id(r, intent)
    configs[r] += (f"router ospf {proc}\n"
                   f" router-id {rid_str}\n"
                   f" exit\n")
    configs[r] += (f"interface Loopback0\n"
                   f" ip ospf {proc} area 0\n"
                   f" exit\n")

print("   -> Activation OSPF sur les liens physiques...")
for link in gns3_data['topology']['links']:
    node_a = link['nodes'][0]
    node_b = link['nodes'][1]
    name_a = nodes_map[node_a['node_id']]
    name_b = nodes_map[node_b['node_id']]

    data_a = get_router_intent(name_a)
    data_b = get_router_intent(name_b)

    if data_a and data_b and data_a['asn'] == data_b['asn']:
        int_a = format_interface(node_a['adapter_number'], node_a['port_number'])
        int_b = format_interface(node_b['adapter_number'], node_b['port_number'])

        configs[name_a] += (f"interface {int_a}\n"
                            f" ip ospf 1 area 0\n"
                            f" mpls ip\n"
                            f"exit\n")
        configs[name_b] += (f"interface {int_b}\n"
                            f" ip ospf 1 area 0\n"
                            f" mpls ip\n"
                            f"exit\n")


# -----------------------------------------------------------------------
print("3. Configuration MPLS et LDP...")
# -----------------------------------------------------------------------
for r in liste_routeurs:
    data = get_router_intent(r)
    if not data: continue

    role = get_router_role(r, intent)
    if role in ('P', 'PE'):
        rid = get_id(r)
        start_label = 100 + (rid - 1) * 200
        end_label = 100 + rid * 200 - 1
        configs[r] += f"mpls label range {start_label} {end_label}\n"
        configs[r] += "mpls label protocol ldp\n"


# -----------------------------------------------------------------------
print("4. Configuration BGP...")
# -----------------------------------------------------------------------
for r in liste_routeurs:
    data = get_router_intent(r)
    if not data: continue

    role = get_router_role(r, intent)
    if role not in ('PE', 'CE'): continue

    asn = data['asn']
    bgp_rid = loopback_ip(r, intent)

    configs[r] += f"! --- BGP ---\n"
    configs[r] += f"router bgp {asn}\n"
    configs[r] += f" bgp router-id {bgp_rid}\n"

    if role == 'PE':
        for other in data['routers']:
            if other == r: continue
            other_role = get_router_role(other, intent)
            if other_role == 'PE':
                n_ip = loopback_ip(other, intent)
                configs[r] += f" neighbor {n_ip} remote-as {asn}\n"
                configs[r] += f" neighbor {n_ip} update-source Loopback0\n"

    for link in gns3_data['topology']['links']:
        node_a_id = link['nodes'][0]['node_id']
        node_b_id = link['nodes'][1]['node_id']
        name_a, name_b = nodes_map[node_a_id], nodes_map[node_b_id]

        if name_a == r:
            neighbor_name = name_b
        elif name_b == r:
            neighbor_name = name_a
        else:
            continue

        neighbor_data = get_router_intent(neighbor_name)
        if not neighbor_data or neighbor_data['asn'] == asn:
            continue

        ip_me, ip_neighbor = link_ips(r, neighbor_name, intent)
        if name_b == r:
            ip_me, ip_neighbor = link_ips(neighbor_name, r, intent)
            ip_me, ip_neighbor = ip_neighbor, ip_me

        configs[r] += f" neighbor {ip_neighbor} remote-as {neighbor_data['asn']}\n"

    configs[r] += " address-family ipv4 unicast\n"
    as_prefix = data.get('prefix', '')
    if as_prefix:
        configs[r] += f"  network {as_prefix}.0.0 mask 255.255.0.0\n"

    for link in gns3_data['topology']['links']:
        node_a_id = link['nodes'][0]['node_id']
        node_b_id = link['nodes'][1]['node_id']
        name_a, name_b = nodes_map[node_a_id], nodes_map[node_b_id]

        if name_a == r:
            neighbor_name = name_b
        elif name_b == r:
            neighbor_name = name_a
        else:
            continue

        neighbor_data = get_router_intent(neighbor_name)
        if not neighbor_data or neighbor_data['asn'] == asn:
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
            if other == r: continue
            other_role = get_router_role(other, intent)
            if other_role == 'PE':
                n_ip = loopback_ip(other, intent)
                configs[r] += f"  neighbor {n_ip} activate\n"
                configs[r] += f"  neighbor {n_ip} send-community\n"
                configs[r] += f"  neighbor {n_ip} next-hop-self\n"
        configs[r] += " exit-address-family\n"

        # AJOUTÉ — address-family ipv4 vrf par VRF portée par ce PE
        pe_vrfs = {}
        for link in gns3_data['topology']['links']:
            node_a_id = link['nodes'][0]['node_id']
            node_b_id = link['nodes'][1]['node_id']
            name_a_l, name_b_l = nodes_map[node_a_id], nodes_map[node_b_id]

            if name_a_l == r:
                ce_candidate = name_b_l
            elif name_b_l == r:
                ce_candidate = name_a_l
            else:
                continue

            if get_router_role(ce_candidate, intent) != 'CE':
                continue

            vrf_name = get_vrf_for_link(r, ce_candidate, intent)
            if not vrf_name:
                continue

            ip_me, ip_ce = link_ips(r, ce_candidate, intent)
            if name_b_l == r:
                ip_me, ip_ce = link_ips(ce_candidate, r, intent)
                ip_me, ip_ce = ip_ce, ip_me

            ce_asn = get_router_intent(ce_candidate)['asn']
            pe_vrfs.setdefault(vrf_name, []).append((ip_ce, ce_asn, ip_me))

        for vrf_name, neighbors in pe_vrfs.items():
            configs[r] += f" address-family ipv4 vrf {vrf_name}\n"
            for ip_ce, ce_asn, ip_me in neighbors:
                subnet = ".".join(ip_me.split(".")[:3]) + ".0"
                configs[r] += f"  network {subnet} mask 255.255.255.252\n"
                configs[r] += f"  neighbor {ip_ce} remote-as {ce_asn}\n"
                configs[r] += f"  neighbor {ip_ce} activate\n"
            configs[r] += " exit-address-family\n"
        # FIN AJOUTÉ

    configs[r] += " exit\n"


# -----------------------------------------------------------------------
print("Génération EEM pour les interfaces actives...")
# -----------------------------------------------------------------------
for r in liste_routeurs:
    if interfaces_actives[r]:
        liste_int = ", ".join(interfaces_actives[r])
        configs[r] += f"""
!
event manager applet GNS3_AUTO_NOSHUT
 event timer countdown time 10
 action 1.0 cli command "enable"
 action 2.0 cli command "configure terminal"
 action 3.0 cli command "interface range {liste_int}"
 action 4.0 cli command "no shutdown"
 action 5.0 cli command "end"
!
"""


# -----------------------------------------------------------------------
print("\nINJECTION DES CONFIGURATIONS")
print(f"Dossier PROJET: {DOSSIER_PROJET}")
# -----------------------------------------------------------------------
for node in gns3_data['topology']['nodes']:
    name = node['name']
    uuid = node['node_id']

    if name in configs:
        final_content = f"""!
version 15.2
service timestamps debug datetime msec
service timestamps log datetime msec
!
hostname {name}
!
boot-start-marker
boot-end-marker
!
no ip domain lookup
ip cef
!
{configs[name]}
!
end
"""
        base_dir   = os.path.join(DOSSIER_PROJET, "project-files", "dynamips", uuid)
        config_dir = os.path.join(base_dir, "configs")

        if os.path.exists(config_dir):
            nvram_file = os.path.join(base_dir, "nvram")
            if os.path.exists(nvram_file):
                try:
                    os.remove(nvram_file)
                    print(f"NVRAM supprimée pour {name}")
                except:
                    pass

            files = [f for f in os.listdir(config_dir) if "startup-config.cfg" in f]
            if files:
                target_file = os.path.join(config_dir, files[0])
            else:
                target_file = os.path.join(config_dir, "i1_startup-config.cfg")

            with open(target_file, 'w') as f:
                f.write(final_content)
            print(f"OK : {name} (UUID: {uuid}) -> Injecté.")
        else:
            print(f"Dossier introuvable pour {name} (UUID: {uuid})")