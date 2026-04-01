import json
import os
import re

# ---------------------------------------------------------------------------
# FONCTIONS UTILITAIRES
# ---------------------------------------------------------------------------
import re

def parse_router_list(input_str):
    """
    Extrait les numéros ou les noms complets (ex: PE1, 1-3).
    """
    routers = []
    # Nettoyage et split
    parts = input_str.replace(" ", "").split(",")

    for part in parts:
        # Cas 1: Déjà un nom complet (ex: PE1, CE2)
        match_named = re.match(r'^([A-Za-z]+)(\d+)$', part)
        if match_named:
            routers.append(part.upper())
            continue

        # Cas 2: Plage numérique (ex: 1-3)
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                for i in range(start, end + 1):
                    routers.append(str(i))
            except ValueError:
                pass
        # Cas 3: Numéro simple
        else:
            clean = re.sub(r'[^0-9]', '', part)
            if clean:
                routers.append(clean)

    return routers

def prefix_routers(routers_raw, role_prefix):
    """
    Ajoute simplement le préfixe à chaque numéro de la liste.
    """
    result = []
    role_prefix = role_prefix.upper()

    for r in routers_raw:
        if re.match(r'^\d+$', r):
            result.append(f"{role_prefix}{r}")
        else:
            # Si l'utilisateur a déjà écrit "PE1", on le garde
            result.append(r.upper())

    # Nettoyage et tri
    result = list(set(result))
    result.sort(key=lambda x: (re.sub(r'\d+', '', x), int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0))
    
    return result

def ask(prompt, default=None):
    """Input avec valeur par défaut affichée."""
    if default:
        val = input(f"{prompt} [Défaut: {default}] : ").strip()
        return val if val else default
    return input(f"{prompt} : ").strip()


# ---------------------------------------------------------------------------
# DÉBUT DU GÉNÉRATEUR
# ---------------------------------------------------------------------------

print("=" * 60)
print("  GÉNÉRATEUR D'INTENT RÉSEAU — MPLS IPv4 (P / PE / CE)")
print("=" * 60)

intent = {
    "project_name": ask("Nom du projet", "Projet_MPLS_IPv4"),
    "global_options": {},   # plus de préfixes IPv6, gardé pour compatibilité
    "as_list": [],
    "bgp_policies": {},
    "external_relationships": [],
    "ospf_custom_metrics": []
}

# ---------------------------------------------------------------------------
# CONFIGURATION DES AS
# ---------------------------------------------------------------------------
print("\n--- CONFIGURATION DES AS ---")
print("Chaque AS regroupe des routeurs de même rôle (P, PE, ou CE).")
print("Rôles disponibles :")
print("  P  -> routeurs cœur MPLS (loopback 10.0.0.x)")
print("  PE -> routeurs de bordure MPLS (loopback 10.123.0.x)")
print("  CE -> routeurs clients (loopback 10.255.0.x)")

while True:
    print(f"\n{'─'*40}")
    print("Ajout d'un nouvel AS  (tapez 'q' pour terminer)")
    asn = ask("Numéro d'AS (ASN)")
    if asn.lower() == 'q':
        break

    # --- Rôle ---
    # --- Rôle ---
    while True:
        role = ask("Rôle des routeurs de cet AS (P ou CE)").upper()
        if role in ("P", "CE"):
            break
        print("  Erreur : choisir P ou CE.")

    all_routers = []

    if role == "P":
        # Saisie pour les routeurs P
        print(f"  -> Entrez les routeurs de type P (Cœur)")
        p_input = ask("Liste des routeurs P (ex: 1-3)")
        p_raw = parse_router_list(p_input)
        all_routers.extend(prefix_routers(p_raw, "P"))

        # Saisie pour les routeurs PE
        print(f"  -> Entrez les routeurs de type PE (Bordure)")
        pe_input = ask("Liste des routeurs PE (ex: 1-5)")
        pe_raw = parse_router_list(pe_input)
        all_routers.extend(prefix_routers(pe_raw, "PE"))
    else:
        # Saisie classique pour CE
        print(f"  -> Entrez les routeurs CE")
        ce_input = ask("Liste des routeurs CE")
        ce_raw = parse_router_list(ce_input)
        all_routers.extend(prefix_routers(ce_raw, "CE"))

    print(f"  -> Routeurs enregistrés : {all_routers}")
# En IPv4 on attend un préfixe de la forme "10.50" -> annoncé en 10.50.0.0/16
    default_prefix = f"10.{asn}"
    prefix = ask(f"Préfixe /16 de l'AS {asn} (ex: 10.{asn} → annonce 10.{asn}.0.0/16)", default_prefix)
    
    # --- Protocole IGP ---
    # Les CE n'ont pas d'IGP interne au cœur MPLS, mais on le demande quand même
    # pour les CE qui ont plusieurs routeurs et font tourner un IGP entre eux.
    while True:
        proto = ask("Protocole IGP (ospf / rip)", "ospf").lower()
        if proto in ("rip", "ospf"):
            break
        print("  Erreur : choisir 'rip' ou 'ospf'.")

    as_obj = {
        "asn": asn,
        "role": role,           # NOUVEAU champ utilisé par RESEAUV5_IPv4.py
        "prefix": prefix,
        "protocol": proto,
        "routers": all_routers
    }

    as_obj["ospf_process_id"] = ask("ID du processus OSPF", "1")

    intent["as_list"].append(as_obj)
    print(f"  ✔ AS {asn} ({role}) ajouté avec {len(all_routers)} routeur(s).")


# ---------------------------------------------------------------------------
# RELATIONS eBGP EXTERNES
# ---------------------------------------------------------------------------
print(f"\n{'─'*40}")
print("--- RELATIONS EXTERNES (eBGP / PEERING / TRANSIT) ---")
print("Déclarez chaque lien entre routeurs de deux AS différents.")
print("La relation est exprimée DU POINT DE VUE du Routeur Source.")
print("  peer     -> égaux (échange routes clients uniquement)")
print("  customer -> le routeur SRC est CLIENT du routeur DST")
print("  provider -> le routeur SRC est FOURNISSEUR du routeur DST")

while True:
    print(f"\nAjout d'une relation eBGP  (tapez 'q' pour terminer)")
    r_src = ask("Routeur Source  (ex: PE1)")
    if r_src.lower() == 'q':
        break
    r_dst = ask("Routeur Destination (ex: CE1)")

    print("  Type : 1. peer   2. customer   3. provider")
    rel_choice = ask("Choix (1/2/3)", "1")
    relationship = {"1": "peer", "2": "customer", "3": "provider"}.get(rel_choice, "peer")

    intent["external_relationships"].append({
        "nodes": [r_src.upper(), r_dst.upper()],
        "relationship": relationship
    })
    print(f"  ✔ {r_src.upper()} ←[{relationship}]→ {r_dst.upper()} enregistré.")
while True:
    vrf = ask("\nAjouter une relation d'une VRF ?")
    vrfRouter = ask("Routeur de la VRF ?")
    if vrf.lower() == 'q':
        break
    else :
        vrf_router = ask(f"Sur quel routeur PE appliquer {vrf.upper()} ? (ex: PE1)")
    
    # On enregistre proprement sans crochets inutiles autour des noms simples
    intent["vrfs"].append({
        "name": vrf.upper(),
        "router": vrf_router.upper()
    })
    
    print(f"   VRF {vrf.upper()} associée à {vrf_router.upper()}")

# ---------------------------------------------------------------------------
# SAUVEGARDE
# ---------------------------------------------------------------------------
output_file = "intent.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(intent, f, indent=4, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"  SUCCÈS ! Fichier '{output_file}' généré.")
print(f"{'='*60}")
print("\nRécapitulatif :")
for as_data in intent["as_list"]:
    print(f"  AS {as_data['asn']:>6} | rôle: {as_data['role']:<3} | "
          f"IGP: {as_data['protocol']:<5} | routeurs: {as_data['routers']}")
print(f"\n  Relations eBGP : {len(intent['external_relationships'])}")
print(f"  Coûts OSPF     : {len(intent['ospf_custom_metrics'])}")
