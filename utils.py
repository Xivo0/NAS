import re


def get_id(nom_routeur):
    match = re.search(r'\d+', nom_routeur)
    return int(match.group()) if match else 0


def format_interface(adapter, port):
    if adapter in (0, 3):
        return f"GigabitEthernet{adapter}/{port}"
    return f"FastEthernet{adapter}/{port}"


def get_router_role(router_name, intent):
    name_up = router_name.upper()
    if name_up.startswith('CE'):
        return 'CE'
    if name_up.startswith('PE'):
        return 'PE'
    if name_up.startswith('P'):
        return 'P'

    for as_data in intent.get('as_list', []):
        if router_name in as_data.get('routers', []):
            role = as_data.get('role', '').upper()
            if role in ('P', 'PE', 'CE'):
                return role
    return 'P'


def get_router_intent(router_name, intent):
    for as_data in intent.get('as_list', []):
        if router_name in as_data.get('routers', []):
            return as_data
    return None


def get_priority(role):
    return {'PE': 3, 'CE': 2, 'P': 1}.get(role, 0)


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
