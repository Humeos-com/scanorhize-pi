# Scanorhize - Hubs

## Description
Programmes qui sont installés sur les Hubs. Les Hubs sont les boitiers à base de Raspberry qui contrôlent les scanners.

## Installation
L'installation d'un Hub se fait par Ansible.
Cette méthode permet de faire évoluer les composants, les configurations et assure la répétabilité du processus.<br>
On peut également mettre à jour un Hub sans recopier toute la carte SD. On conserve ainsi la configuration des scanners et les logs tout en faisant évoluer le système.


### Prérequis
Les programmes gèrent différentes configurations matérielles parmi les suivantes:
- Raspberry Pi 4 ou Pi 5 en Debian 12 32 bits pour les drivers Epson (64 bits si on n'utilise que des scanners Canon Lide)
- Carte RTC WittyPi 3, 4 ou 4L3V7
- carte d'extention de ports USB UUGEAR Big 7 ou Mega 4
- Carte relai RPi Relay Board ou SBComponent PiRelay-V2

### Configuration du GPIO

Selon les composants utilisés pour le boitier, les GPIO utilisés sont différents.

#### Charging and standby pins for Witty Pi L3V7
* CHRG_PIN: int = 5  # input to detect charging status
* STDBY_PIN: int = 6  # input to detect standby status

#### Mode Configuration
Le fait d'allumer le boitier avec le bouton ON/OFF active le mode configuration automatiquement. On détecte au démarrage du Raspberry qu'il a été allumé par appui sur le bouton d'allumage de la carte Witty Pi.<br>
En mode configuration le premier relai qui s'allume et le relai de la clé 4G alors qu'en mode acquisition ce sont les relais des scanners actifs qui s'allument séquentiellement, puis la clé 4G s'allume en dernier pour la transmission des données.<br>

ATTENTION: lorsqu'on lance le mode configuration le boitier s'arrête au bout de 20 minutes par sécurité (sinon il ne s'arrêterait pas et viderait la batterie)
Il est recommandé de l'arrêter avant par l'interface Web, avec le bouton Poweroff, ou avec le bouton ON/OFF du boitier.

#### Démarrage / Arrêt du boitier
L'ancien modèle dispose d'un bouton de coupure physique de l'alimentation (ON/OFF).
Cette technique permet de s'assurer que le boitier redémarre quelque soit son état.
L'horloge du Witty Pi 3 ou 4 étant sauvegardée par une pile CR2032, il n'y a aucun 
problème de synchronisation du temps lors d'un arrêt/redémarrage.

Sur les modèles équipés de cartes Witty Pi L3V7, si on veut couper l'alimentation,
il faut couper le 5V et la batterie, ce qui n'est pas simple et en plus on perd
l'heure sur l'horloge. On utilise donc un bouton qui agit sur GPIO-7 (pin physique 7) avec mise à la terre, pour faire les arrêts/relances, sans jamais couper l'alimentation. Ce qui peut conduire dans certains cas à des difficultés à éteindre ou allumer le boitier.
Quand la pression sur le bouton poussoir ne produit aucun effet, il faut presser le bouton pendant au moins 10 secondes pour forcer l'arrêt ou le démarrage.

#### Pour le relai Banggood
pins BCM
- Ch1Pin = 19  # Scanner1
- Ch2Pin = 26  # Scanner2
- Ch3Pin = 20  # Scanner3
- Ch4Pin = 21  # Clé 4G
- PinArray = [19, 26, 20, 21]

#### Pour le relai SBComponent RelayPi-V2
pins BCM
- Ch1Pin = 13  # Scanner1
- Ch2Pin = 22  # Scanner2<br>
Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
et cabler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des cables Dupont
- Ch3Pin = 27  # Scanner3
- Ch4Pin = 19  # Clé 4G
- PinArray = [13, 22, 27, 19]


#### Pour l'alimentation de la carte WittyPi L3V7
Pins BCM
- CHRG_PIN = 5  # input to detect charging status
- STDBY_PIN = 6  # input to detect standby status<br>
Pour les explications, voir le programme wittyPi.sh fourni par UUGEAR

#### Carte USB Big 7
Selon les connexions sur la carte USB Big 7<br>
Ici la clé 4G se trouve sur le port USB1 de la carte Big 7
configuration des ports USB de la carte Big 7<br>
- USB1: Clé 4G BCM pin 19
- USB2: Scanner 1 BCM pin 13
- USB3: Scanner 2 BCM pin 22
- USB4: Scanner 3 BCM pin 27
- USB5: non câblé
- USB6: non câblé
- USB7: non câblé



### Étapes

## Utilisation
Au démarrage du Raspberry, on lance la commande /home/pi/Scanorhize/StartScanorhize.sh<br>
Ce shell lance ScanorhizeStart.py qui gère les heures de reveil et d'endomissement du Hub et qui selon le mode de démarrage (apui sur le bouton ON/OFF ou réveil programmé) va lancer le serveur Flask si on est en mode configuration
ou l'acquisition d'images par les scanners.<br>
Le serveur Flask est lancé par la commande Scanorhize.py et l'acquisition par ScanorhizeProcess.py<br>



## Fonctionnalités

Il existe 2 modes de fonctionnement sur les boitiers :
- le mode configuration qui permet de créer un point d'accès Wifi et de se connecter au Raspberry à travers le serveur Web Flask ou par SSH depuis le serveur backend-prod.humeos.com lorsque la connectivité 4G est correcte.
- le mode nominal qui réveille le Raspberry pour faire les acquisitions puis éteint le boitier jusqu'à la nouvelle période.

### Mode configuration
Pour se connecter au Raspberry quand il est en  mode configuration, il faut se connecter à son Wifi: Scanorhize
On obtient alors une IP en 192.168.1.x et on peut accéder au Raspberry sur l'IP 192.168.1.42<br>
L'utilisateur du système est pi<br>
En mode configuration, on peut exécuter les commandes du Raspberry en se connectant en SSH ou bien utiliser le serveur Web Flask.<br>

On accède à l'interface d'Administration locale du boitier par l'URL:<br>
http://192.168.1.42:8080

On peut aussi accéder au Raspberry depuis le serveur backend-prod.humeos.com si on connaît le port utilisé par le Raspberry. On peut découvrir le port avec la commande suivante sur le serveur:
```
debian@d2-2-gra11:~$ sudo netstat -tanpl | grep ":22" | grep -v 2222
tcp        0      0 127.0.0.1:2269          0.0.0.0:*               LISTEN      1040576/sshd: debia 
tcp6       0      0 ::1:2269                :::*                    LISTEN      1040576/sshd: debia 
debian@d2-2-gra11:~$ 
```
Ici, on voit que la connexion se trouve sur le port 2269.<br>
Pour se connecter au Raspberry, on peut lancer un SSH de la forme:
```
debian@d2-2-gra11:~$ ssh pi@localhost -p 2269
```
Les clés d'accès sont configurées sur le compte de l'utilisateur debian sur le serveur backend-prod.humeos.com et permettent d'accèder au Hub sans mot de passe.

### Mode nominal

## Exemples de code

## Contribuer

## Licence

## Crédits

# test
