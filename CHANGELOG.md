# Changelog

## TODO

Passer les commandes WittyPi en Python plutôt qu'en ligne de commande Shell
Créer un mode "continue" pour tester l'acquisition sans faire le shutdown du Raspberry
Créer un RAMDisk et modifier l'écriture des images


## 2025-02-19

Fin du travail de réécriture pour PyLint

### Added
Addition du fichier de configuration Server.json pour les paramètres de la SIM
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



