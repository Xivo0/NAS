import os

DOSSIER_PROJET = r"/mnt/c/Users/laixa/GNS3/projects/NASDemo"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

FICHIER_INTENT = os.path.join(SCRIPT_DIR, "intent.json")
FICHIER_GNS3 = os.path.join(DOSSIER_PROJET, "NASDemo.gns3")

if not os.path.exists(FICHIER_INTENT):
    FICHIER_INTENT = os.path.join(DOSSIER_PROJET, "intent.json")
if os.path.exists(os.path.join(SCRIPT_DIR, "NASDemo.gns3")):
    FICHIER_GNS3 = os.path.join(SCRIPT_DIR, "NASDemo.gns3")

DOSSIER_SORTIE = os.path.join(DOSSIER_PROJET, "configs_finales")
