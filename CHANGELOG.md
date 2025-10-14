# Changelog

## TODO
Créer un RAMDisk et modifier l'écriture des images.
Ajouter des vignettes pour les images.
Avoir plusieurs séquenceurs pour envoyer les vignettes, les infos du Hub, les images.


## 2025-10-14 / v0.9.43
Correctifs mineurs:
On abandonne le nom duckdns.org dans l'initialisation du Hub.
Le tunnel SSH est encadré par un try/catch pour la connectivité 4G.

## 2025-10-08 / v0.9.38
Le port SSH utilisé pour le tunnel créé par le Hub sur backend-prod.humeos.com devient aléatoire entre 2223 et 2299 à chaque fois qu'on redémarre le mode configuration. Ceci afin d'éviter que si on lance le mode configuration 2 fois de suite on se trouve avec un tunnel bloqué par la première connexion. A noter qu'avant, ce port était aléatoire au premier lancement, puis stocké dans le fichier Hub.json. On savait ainsi quel Hub était connecté.

## 2025-10-03 / v0.9.36
Modification du calcul de la capacité de la batterie en fonction du voltage. On Affiche 0% à 3,2V et 100% à 4,2V. C'est une fonction linéaire, donc qui n'est pas réaliste, mais qui permet de savoir quand la batterie est faible. Car à 3,1V, le WittyPi coupe l'alimentation pour préserver la batterie, ce qui peut arriver pendant le fonctionnement lorsqu'on démarre le Hub avec 3,2V.

## 2025-09-26 / v0.9.33
On passe à 4800dpi. Les choix de résolution sont:
300 / 600 / 1200 / 2400 /4800

## 2025-08-21
Passage en Python de l'interface WittyPy avec le programme WittyPy_utilities.py
Ce programme permet d'afficher les valeurs de la carte WittyPi et de configurer la carte.
Ainsi, on peut configurer la carte WittyPi par Ansible sans passer par WittyPi.sh

## 2025-08-09 v0.9.10-beta 
Tous les composants nécessaires à Flask (Bootstrap) deviennent des ressources locales. Ainsi, on peut voir l'interface Flask même s'il n'y a pas de connexion Internet. C'est le cas, lorsque la clé 4G n'a pas de connectivité.
Il y a également un mode d'acquisition forcée, indépendant des alarmes, qui permet de lancer l'acquisition et tester ainsi le bon fonctionnement des scanners lors d'une intervention sur le Hub.
Quand on allume le Hub avec le bouton, il passe automatiquement en mode configuration. C'est à dire que l'application Flask se lance sur http://192.168.1.42:8080 pour configurer le Hub. Dans le mode configuration le Hub s'éteint automatiquement au bout de 20 minutes si on oublie d'appuyer sur le bouton "Poweroff".

## 2025-07-10 v0.9.0 stable 
Découpage du fonctionnement de l'acquisition.
Le programme principal ScanorhizeStart.py gére les heures de reveil et lance l'acquisition par ScanorhizeProcess.py.
Si ce dernier rencontre un souci, plantage, etc... ScanorhizeStart.py continue et finit les tâches comme l'heure du prochain reveil puis éteint le Hub. Ainsi, lors d'un plantage sur l'acquisition, le Hub ne reste plus allumé...
Mise en place de flags sur l'interface Flask de manière à pouvoir travailler sans connectivité.
Création d'un tunnel SSH inverse sur le serveur backend-prod.humeos.com de manière à prendre la main sur le Hub en mode configuration.
Une partie des commandes WittyPi passe désormais par le Python (WittyPython.py) afin d'éviter de lancer les Shells.

## 2025-04-09 v0.8.0-beta S3
Utilisation de S3 pour stocker les images

## 2025-02-19

Fin du travail de réécriture pour PyLint

### Added
Addition du fichier de configuration Hub.json pour les paramètres du Raspberry et de la carte SIM
Création des modules pour séparer les imports
Addition du menu "Server" dans l'application Flask
Addition de méthodes main pour tests unitaires
Addition des imports fake_rpi et smbus2 pour tester sous MacOSX

### Changed
Passage des dates en Timstamp Unix (Epoch 1970) plutôt que depuis l'an 0 afin de bénéficier des librairies de conversion standards

### Fixed
Addition des méthodes de la carte SIM pour faire tourner le serveur Flask

### Removed


## 2024-11-08

Début du travail de réécriture pour PyLint
Création des 2 scripts powerinfo.py et powerdown.py pour tester les scanners et les ports USB

## 2024-11-19

Récupération des sources d'origine depuis un des boitiers
Tous les fichiers sont datés de 24-08-2020 à 02-03-2021
Commit initial



