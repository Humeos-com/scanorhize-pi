# Scanorhize - Raspberry

## Description
Programmes qui sont installés sur le Raspberry

## Installation
L'installation se fait pas copie de la SDCard...

### Prérequis

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
On obtient alors une IP en 192.168.0.x et on peut accéder au Raspberry sur l'IP 192.168.0.10
L'utilisateur du système est pi
En mode configuration, on peut exécuter les commandes du Raspberry en se connecter en SSH ou bien
utiliser le serveur Web Flask qui tourne sur le port 8080

### Mode nominal

## Exemples de code

## Contribuer

## Licence

## Crédits

