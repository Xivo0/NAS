from utils import get_router_role, get_priority, get_id

_subnet_counter_mpls = -1
_subnet_counter_ce = -1
_subnet_cache = {}
_subnet_counter_mpls_link = 0
_subnet_counter_ce_link = 0
_link_ip_cache = {}


def get_link_subnet(name_a, name_b, role_a, role_b):
    global _subnet_counter_mpls, _subnet_counter_ce, _subnet_counter_mpls_link, _subnet_counter_ce_link

    key = frozenset([name_a, name_b])
    if key in _subnet_cache:
        return _subnet_cache[key]

    mpls_roles = {'P', 'PE'}
    if role_a in mpls_roles and role_b in mpls_roles:
        if _subnet_counter_mpls_link % 64 == 0:
            _subnet_counter_mpls += 1
        base = f"10.1.{_subnet_counter_mpls}"
        is_ce = False
    else:
        if _subnet_counter_ce_link % 64 == 0:
            _subnet_counter_ce += 1
        base = f"192.168.{_subnet_counter_ce}"
        is_ce = True

    _subnet_cache[key] = (base, is_ce)
    return (base, is_ce)


def link_ips(name_a, name_b, intent):
    global _subnet_counter_mpls_link, _subnet_counter_ce_link, _link_ip_cache

    key = tuple(sorted([name_a, name_b]))
    if key in _link_ip_cache:
        addr_a, addr_b = _link_ip_cache[key]
        if name_a == key[0]:
            return addr_a, addr_b
        return addr_b, addr_a

    role_a = get_router_role(name_a, intent)
    role_b = get_router_role(name_b, intent)
    prio_a = get_priority(role_a)
    prio_b = get_priority(role_b)
    base, is_ce = get_link_subnet(name_a, name_b, role_a, role_b)
    start_octet = _subnet_counter_ce_link if is_ce else _subnet_counter_mpls_link

    if prio_a > prio_b:
        addr_a, addr_b = f"{base}.{start_octet + 1}", f"{base}.{start_octet + 2}"
    elif prio_b > prio_a:
        addr_a, addr_b = f"{base}.{start_octet + 2}", f"{base}.{start_octet + 1}"
    else:
        if get_id(name_a) < get_id(name_b):
            addr_a, addr_b = f"{base}.{start_octet + 1}", f"{base}.{start_octet + 2}"
        else:
            addr_a, addr_b = f"{base}.{start_octet + 2}", f"{base}.{start_octet + 1}"

    if is_ce:
        n_a = _subnet_counter_ce_link + 2
        n_b = _subnet_counter_ce_link + 1
        addr_pair = (f"{base}.{n_a}", f"{base}.{n_b}")
        _subnet_counter_ce_link = (_subnet_counter_ce_link + 4) % 256
    else:
        n_a = _subnet_counter_mpls_link + 1
        n_b = _subnet_counter_mpls_link + 2
        addr_pair = (f"{base}.{n_a}", f"{base}.{n_b}")
        _subnet_counter_mpls_link = (_subnet_counter_mpls_link + 4) % 256

    _link_ip_cache[key] = addr_pair
    if name_a == key[0]:
        return addr_pair
    return addr_pair[1], addr_pair[0]
