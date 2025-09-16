# Scanorhize - Hubs

## Description
Dans le projet Scanorhize, les Hubs sont les boitiers qui contrôlent les scanners et qui transmettent les images à la plateforme Web.
Ils sont composés de Raspberry Pi, d'une une carte Witty Pi pour l'horloge temps réelle, d'une carte relais et d'une carte Big 7 qui fournit des ports USB additonnels.
La contrainte des Hubs est la gestion de l'alimentation qui doit être minimale afin qu'ils puissent fonctionner en autonomie sur les terres agricoles.
Le principe de fonctionnement est que la carte Witty Pi est programmée pour des réveils périodiques. Au réveil, le Raspberry démarre, sans alimenter aucun port USB des scanners ni de la clé 4G pour la communication Internet.
Le Rasberry va faire ses acquisition en allumant les scanners un par un grâce à la carte relai. Une fois les acquisitions terminées, le Raspberry allume la clé 4G pour envoyer des données et récupérer certains éléments selon la configuration du Hub.

## Premiers pas
La première étape consiste à mettre le Hub en mode configuration afin de contrôler ou modifier son paramètrage. Lorsque le Hub est éteint, il faut appuyer sur le bouton qui se trouve près des connecteurs USB, pour démarrer le Hub en mode configuration.
Le Hub va essayer de détecter les scanners qui sont branchés sur ses ports USB, puis va lancer une application Web pour sa configuration. Cette application est accessible par le Wifi "Scanorhize" sur l'Url: http://192.168.1.42:8080/ <br>
Saisir les période de réveil pour chacun des scanners, enregistrer les configurations sur le serveur.<br>
Une fois tous les paramètres saisis, les scanners et le Hub en place, on peut aller sur le menu "Hub", pour lancer une acquisition afin de s'assurer que tout fonctionne bien.<br>
Enfin, il faut éteindre le Hub afin de préserver la batterie. Cliquer sur le bouton rouge "Power off". On ne doit plus voir aucune led allumée sur le Hub.
Par la suite, le Hub va se réveiller selon sa programmation, faire des acquisitions et envoyer ses données au serveur.



## Détail du fonctionnement

Au démarrage du Raspberry, on lance la commande /home/pi/Scanorhize/StartScanorhize.sh<br>
Ce shell lance ScanorhizeStart.py qui gère les heures de reveil et d'endormissement du Hub et qui selon le mode de démarrage (apui sur le bouton ON/OFF ou réveil programmé) va lancer l'aquisition des images par le scanner ou le serveur Web en mode configuration.<br>
Le serveur Flask est lancé par la commande Scanorhize.py et l'acquisition par ScanorhizeProcess.py<br>



#### Mode Configuration
Le fait d'allumer le boitier avec le bouton ON/OFF active le mode configuration automatiquement. On détecte au démarrage du Raspberry qu'il a été allumé par appui sur le bouton d'allumage de la carte Witty Pi.<br>
En mode configuration, le relai de chaque scanner s'allume afin de détecter les scanners branchés sur le Hub. En dernier lieu, c'est le relai de la clé 4G qui s'allume.<br>

ATTENTION: lorsqu'on lance le mode configuration le boitier s'arrête au bout de 20 minutes par sécurité (sinon il ne s'arrêterait pas et viderait la batterie)
Il est recommandé de l'arrêter avant par l'interface Web, avec le bouton Poweroff, ou avec le bouton ON/OFF du boitier.

### Mode nominal (acquisitions)
Le mode nominal réveille le Hub pour faire les acquisitions puis éteint le boitier jusqu'au prochain réveil programmé.

#### Démarrage / Arrêt du boitier
On utilise donc un bouton qui agit sur GPIO-7 (pin physique 7) avec mise à la terre, pour faire les arrêts/relances, sans jamais couper l'alimentation. Ce qui peut conduire dans certains cas à des difficultés à éteindre ou allumer le boitier.
> [!TIP]
> Quand la pression sur le bouton poussoir ne produit aucun effet, il faut presser le bouton pendant au moins 10 secondes pour forcer l'arrêt ou le démarrage.




## Installation
L'installation d'un Hub se fait par Ansible. Les sources se trouvent sur: https://github.com/arditial/ansible-arditi <br>
Cette méthode permet de faire évoluer les composants, les configurations et assure la répétabilité du processus.<br>
On peut également mettre à jour un Hub sans recopier toute la carte SD. On conserve ainsi la configuration des scanners et les logs tout en faisant évoluer le système.
A la base, il faut quand même une image Debian raspios-bookworm-armhf-lite sur la SD Card du Raspberry, en 32 bits pour les drivers Epson.


### Prérequis
Les programmes gèrent différentes configurations matérielles parmi les suivantes:
- Raspberry Pi 4 ou Pi 5 en Debian 12 32 bits pour les drivers Epson (64 bits si on n'utilise que des scanners Canon Lide)
- Carte RTC WittyPi 3, 4 ou 4L3V7
- carte d'extention de ports USB UUGEAR Big 7 ou Mega 4
- Carte relai RPi Relay Board ou SBComponent PiRelay-V2


### Configuration du GPIO
Selon les composants utilisés pour le boitier, les GPIO utilisés sont différents.

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





## Fonctionnalités

Il existe 2 modes de fonctionnement sur les boitiers :
- le mode configuration qui permet de créer un point d'accès Wifi et de se connecter au Raspberry à travers le serveur Web Flask ou par SSH depuis le serveur backend-prod.humeos.com lorsque la connectivité 4G est correcte.
- l

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
