# NAS

MPLS/LDP a été implémenté.

OSPF:
Router-id:
  PE: 1.0.0.X puis 1.0.X.255 quand +255 routeurs puis 1.X.255.255 quand +510 routeurs
  P: 10.0.0.X puis 10.0.X.255 quand +255 routeurs puis 10.X.255.255 quand +510 routeurs

Loopback:
  P: 10.0.X.X/32
  PE: 10.123.X.X/32
  CE: 10.255.X.X/32 (ou alors ça sera configuré par le client)

Adressage réseau:
  Routeurs dans réseau MPLS:
    10.1.0.X/30 -> 10.1.X.255/30 quand +64 liens réseau (un réseau = un lien = 2 routeurs)

  Entre PE et CE:
    192.168.0.X/30 -> 192.168.X.255/30 quand +64 liens réseau
  
