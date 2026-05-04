import json
import os
import re

# ---------------------------------------------------------------------------
# FONCTIONS UTILITAIRES
# ---------------------------------------------------------------------------

def parse_router_list(input_str):
    """Extrait les numéros ou les noms complets (ex: PE1, 1-3)."""
    routers = []
    parts = input_str.replace(" ", "").split(",")
    for part in parts:
        match_named = re.match(r'^([A-Za-z]+)(\d+)$', part)
        if match_named:
            routers.append(part.upper())
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                for i in range(start, end + 1):
                    routers.append(str(i))
            except ValueError:
                pass
        else:
            clean = re.sub(r'[^0-9]', '', part)
            if clean.isdigit():
                routers.append(clean)
    return routers

def prefix_routers(routers_raw, role_prefix):
    """Ajoute le préfixe aux numéros simples et trie la liste."""
    result = []
    for r in routers_raw:
        if re.match(r'^\d+$', r):
            result.append(f"{role_prefix.upper()}{r}")
        else:
            result.append(r.upper())
    # Tri numérique intelligent pour éviter PE10 avant PE2
    result = list(set(result))
    result.sort(key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))
    return result

def ask(prompt, default=None):
    """Input avec valeur par défaut affichée."""
    if default:
        val = input(f"{prompt} [Défaut: {default}] : ").strip()
        return val if val else default
    return input(f"{prompt} : ").strip()


def configure_vrf_list():
    """Remplit la section vrf_list avec RD et RT."""
    print(f"\n{'─'*40}")
    print("--- DÉFINITION DES VRF (vrf_list) ---")
    while True:
        name = ask("Nom de la VRF (ex: Client_A, ou 'q' pour finir)")
        if name.lower() == 'q': break
        
        rd = ask(f"RD pour {name.upper()} ")
        rt_exp = ask(f"RT Export pour {name.upper()} ")
        rt_imp = ask(f"RT Import pour {name.upper()}")
          
        intent["vrf_list"].append({
            "name": name, # On garde la casse pour correspondre à l'image
            "rd": rd,
            "rt_export": rt_exp,
            "rt_import": rt_imp
        })

def configure_vrf_assignments():
    """Associe les liens PE-CE à une VRF (vrf_assignments)."""
    print(f"\n{'─'*40}")
    print("--- ASSIGNATION DES VRF AUX LIENS (vrf_assignments) ---")
    while True:
        pe = ask("Nom du PE (ex: PE1, ou 'q' pour finir)").upper()
        if pe.lower() == 'q': break
        
        ce = ask(f"Nom du CE connecté à {pe} (ex: CE1)").upper()
        vrf_name = ask(f"Nom de la VRF à appliquer sur ce lien (ex: Client_A)")
        
        intent["vrf_assignments"].append({
            "pe": pe,
            "ce": ce,
            "vrf": vrf_name
        })

# ---------------------------------------------------------------------------
# DÉBUT DU GÉNÉRATEUR
# ---------------------------------------------------------------------------

print("=" * 60)
print("  GÉNÉRATEUR D'INTENT RÉSEAU — MPLS IPv4 (P / PE / CE)")
print("=" * 60)

intent = {
    "project_name": ask("Nom du projet", "Projet_MPLS_IPv4"),
    "global_options": {},
    "as_list": [],
    "vrfs": [], # Section VRF ajoutée
    "bgp_policies": {},
    "external_relationships": [],
    "ospf_custom_metrics": [],
    "vrf_list": [],
    "vrf_assignments": []
}

# ---------------------------------------------------------------------------
# CONFIGURATION DES AS
# ---------------------------------------------------------------------------
print("\n--- CONFIGURATION DES AS ---")

while True:
    print(f"\n{'─'*40}")
    print("Ajout d'un nouvel AS  (tapez 'q' pour terminer)")
    asn = ask("Numéro d'AS (ASN)")
    if asn.lower() == 'q':
        break

    # --- Rôle ---
    while True:
        role = ask("Rôle principal de l'AS (P ou CE)").upper()
        if role in ("P", "CE"):
            break
        print("  Erreur : choisir P (pour Cœur/Bordure MPLS) ou CE (Client).")

    all_routers = []
    if role == "P":
        # Saisie dissociée pour les P et les PE
        print("  -> Configuration des routeurs du Cœur MPLS")
        p_input = ask("Liste des routeurs P (ex: 1-2)")
        all_routers.extend(prefix_routers(parse_router_list(p_input), "P"))

        print("  -> Configuration des routeurs de Bordure (PE)")
        pe_input = ask("Liste des routeurs PE (ex: 1-5)")
        all_routers.extend(prefix_routers(parse_router_list(pe_input), "PE"))
    else:
        # Saisie classique pour les CE
        ce_input = ask("Liste des routeurs CE (ex: 1-3)")
        all_routers.extend(prefix_routers(parse_router_list(ce_input), "CE"))

    intent["as_list"].append({
        "asn": int(asn) if asn.isdigit() else asn,
        "role": role,
        "routers": all_routers
    })
# ---------------------------------------------------------------------------
# POLITIQUES BGP (Indispensable pour MPLS)
# ---------------------------------------------------------------------------
print(f"\n{'─'*40}")
intent["bgp_policies"] = {
    "customer_community": ask("Community Client", "100:10"),
    "local_pref_customer": int(ask("Local Pref Client", "200")),
    "local_pref_peer": int(ask("Local Pref Peer", "100")),
    "local_pref_provider": int(ask("Local Pref Provider", "50"))
}

# ---------------------------------------------------------------------------
# RELATIONS eBGP & VRF (Le coeur de la config)
# ---------------------------------------------------------------------------
print(f"\n--- RELATIONS eBGP EXTERNES ---")
while True:
    r_src = ask("Routeur Source (ex: PE1, 'q' pour finir)")
    if r_src.lower() == 'q': break
    r_dst = ask("Routeur Destination (ex: CE1)")
    rel_choice = ask("Type (1:peer, 2:customer, 3:provider)", "1")
    rel = {"1": "peer", "2": "customer", "3": "provider"}.get(rel_choice, "peer")
    intent["external_relationships"].append({"nodes": [r_src.upper(), r_dst.upper()], "relationship": rel})

# Appel des nouvelles fonctions VRF (celles de l'image)
configure_vrf_list()
configure_vrf_assignments()

# ---------------------------------------------------------------------------
# SAUVEGARDE
# ---------------------------------------------------------------------------
with open("intent.json", 'w', encoding='utf-8') as f:
    json.dump(intent, f, indent=4, ensure_ascii=False)

print(f"\n Le fichier 'intent.json' est prêt.")