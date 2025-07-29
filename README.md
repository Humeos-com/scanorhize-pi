# Scanorhize - Raspberry

## Description
Programmes qui sont installés sur le Raspberry

## Installation
L'installation se fait par copie de la SDCard...ou par Ansible

### Prérequis
- Avoir un boitier Raspberry Pi 4 ou Pi 5 avec une carte WittyPi 3, 4 ou 4L3V7.
- Avoir une carte d'extention de ports USB UUGEAR Big 7 ou Mega 4
- Avoir une carte relai RPi Relay Board ou SBComponent PiRelay-V2

### Configuration du GPIO

Selon les composants utilisés pour fabriquer le boitier, les GPIO utilisés sont différents.

#### Charging and standby pins for Witty Pi L3V7
* CHRG_PIN: int = 5  # input to detect charging status
* STDBY_PIN: int = 6  # input to detect standby status

#### Mode Configuration
On peut mettre le boitier en mode configuration si on laisse le GPIO
concernée sur le 0V (GND) au démarrage de l'application.
Il faut donc laisser le bouton config appuyé pendant 2 minutes suite au démarrage du boitier.
On entend alors un relai qui claque.
Sur les anciens boitiers WittyPi_3, on utilise GPIO-17 (pin physique 11)
Sur les nouveaux boitiers on utilise GPIO-16 (pin physique 36 + ground 34)<br>

ATTENTION: lorsqu'on lance le mode configuration le boitier s'arrête au bout de 20 minutes par sécurité (sinon il ne s'arrêterait pas et viderait la batterie)
Il est recommandé de l'arrêter avant par l'interface Web, avec le bouton Poweroff

#### Démarrage / Arrêt du boitier
L'ancien modèle dispose d'un bouton de coupure physique de l'alimentation (ON/OFF).
Cette technique permet de s'assurer que le boitier redémarre quelque soit son état.
L'horloge du Witty Pi 3 ou 4 étant sauvegardée par une pile CR2032, il n'y a aucun 
problème de synchronisation du temps lors d'un arrêt/redémarrage.

Sur les modèles équipés de cartes Witty Pi L3V7, si on veut couper l'alimentation,
il faut couper le 5V et la batterie, ce qui n'est pas simple et en plus on perd
l'heure sur l'horloge. On utilise donc un bouton qui agit sur GPIO-7 (pin physique 7) avec mise à la terre,
pour faire les arrêts/relances, sans jamais couper l'alimentation. Ce qui peut conduire dans certains
cas à des difficultés à éteindre ou allumer le boitier.
Quand la pression sur le bouton poussoir ne produit aucun effet, on peut essayer de presser le bouton
pendant 10 secondes.

#### Pour le relai Banggood initial
pins BCM
- Ch1Pin = 19  # Scanner1
- Ch2Pin = 26  # Scanner2
- Ch3Pin = 20  # Scanner3
- Ch4Pin = 21  # Clé 4G
- PinArray = [19, 26, 20, 21]

#### Pour le relai SBComponent RelayPi-V2
pins BCM
- Ch1Pin = 19  # Scanner1
- Ch2Pin = 13  # Scanner2<br>
Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
et cabler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des cables Dupont
- Ch3Pin = 22  # Scanner3
- Ch4Pin = 27  # Clé 4G
- PinArray = [19, 13, 22, 27]

#### Pour l'alimentation de la carte WittyPi L3V7
Pins BCM
- CHRG_PIN = 5  # input to detect charging status
- STDBY_PIN = 6  # input to detect standby status<br>
Pour les explications, voir le programme wittyPi.sh fourni par UUGEAR

#### Carte USB Big 7
Selon les connexions sur la carte USB Big 7<br>
Ici la clé 4G se trouve sur le port USB1 de la carte Big 7
configuration des ports USB de la carte Big 7<br>
DEFAULT_PIN_ARRAY = [13, 22, 27, 19]



### Étapes

## Utilisation
Au démarrage du Raspberry on lance la commande /home/pi/Scanorhize/StartScanorhize.sh
Cette commande lance le serveur Flask si on est en mode configuration (bouton appuyé 30 sec après l'allumage)
ou lance l'acquisition en fonction des périodes pour chaque scanner.
Une fois l'acquisition effectuée et l'image postée sur la plateforme Web, le Raspberry s'éteint jusqu'au prochain réveil
déclenché par la carte WittyPi.

## Fonctionnalités

Il existe 2 modes de fonctionnement sur les boitiers :
- le mode configuration qui permet de créer un point d'accès Wifi et de se connecter au Raspberry à travers une application Web
- le mode nominal qui réveille le Raspberry pour faire les acquisitions puis éteint le boitier jusqu'à la nouvelle période.

### Mode configuration
Pour se connecter au Raspberry en mode configuration, il faut se connecter à son Wifi : Scanorhize
On obtient alors une IP en 192.168.0.x et on peut accéder au Raspberry sur l'IP 192.168.0.10.<br>
A noter que l'IP dépend des clés 4G/Wifi. Selon le modèle on peut avoir une IP en 192.168.1.X.<br>
L'utilisateur du système est pi
En mode configuration, on peut exécuter les commandes du Raspberry en se connecter en SSH ou bien utiliser le serveur Web Flask qui tourne sur le port 8080.<br>

On accède à l'interface d'Administration locale du boitier par l'URL:<br>
http://192.168.X.Y:8080


### Mode nominal

## Exemples de code

## Contribuer

## Licence

## Crédits

# test
