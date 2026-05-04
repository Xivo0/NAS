from utils import get_router_role


def get_vrf_list(intent):
    return intent.get('vrf_list', [])


def get_vrf_for_link(pe_name, ce_name, intent):
    for assignment in intent.get('vrf_assignments', []):
        if assignment['pe'] == pe_name and assignment['ce'] == ce_name:
            return assignment['vrf']
    return None


def generate_vrf_config(liste_routeurs, intent):
    vrf_configs = {}
    vrf_list = get_vrf_list(intent)
    if not vrf_list:
        return vrf_configs

    for r in liste_routeurs:
        role = get_router_role(r, intent)
        if role != 'PE':
            continue

        pe_vrfs = {a['vrf'] for a in intent.get('vrf_assignments', []) if a['pe'] == r}
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
