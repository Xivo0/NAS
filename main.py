import json
import os

from config import DOSSIER_PROJET, FICHIER_GNS3, FICHIER_INTENT
from utils import get_id
from vrf import generate_vrf_config
from generators import (
    generate_loopbacks,
    generate_interfaces,
    generate_ospf,
    generate_mpls,
    generate_bgp,
    generate_eem,
)

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

print("0. Configuration des VRF...")
for r, vrf_cfg in generate_vrf_config(liste_routeurs, intent).items():
    configs[r] += vrf_cfg

print("1. Configuration des IPs et Loopbacks (IPv4)...")
generate_loopbacks(liste_routeurs, configs, intent)
generate_interfaces(gns3_data, nodes_map, configs, interfaces_actives, intent)

print("2. Configuration OSPF en IPv4...")
generate_ospf(liste_routeurs, gns3_data, nodes_map, configs, intent)

print("3. Configuration MPLS et LDP...")
generate_mpls(liste_routeurs, configs, intent)

print("4. Configuration BGP...")
generate_bgp(liste_routeurs, gns3_data, nodes_map, configs, intent)

print("Génération EEM pour les interfaces actives...")
generate_eem(liste_routeurs, configs, interfaces_actives)

print("\nINJECTION DES CONFIGURATIONS")
print(f"Dossier PROJET: {DOSSIER_PROJET}")

for node in gns3_data['topology']['nodes']:
    name = node['name']
    uuid = node['node_id']

    if name not in configs:
        continue

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
    base_dir = os.path.join(DOSSIER_PROJET, "project-files", "dynamips", uuid)
    config_dir = os.path.join(base_dir, "configs")

    if not os.path.exists(config_dir):
        print(f"Dossier introuvable pour {name} (UUID: {uuid})")
        continue

    nvram_file = os.path.join(base_dir, "nvram")
    if os.path.exists(nvram_file):
        try:
            os.remove(nvram_file)
            print(f"NVRAM supprimée pour {name}")
        except Exception:
            pass

    files = [f for f in os.listdir(config_dir) if "startup-config.cfg" in f]
    target_file = os.path.join(config_dir, files[0] if files else "i1_startup-config.cfg")

    with open(target_file, 'w') as f:
        f.write(final_content)
    print(f"OK : {name} (UUID: {uuid}) -> Injecté.")
