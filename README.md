# Scanorhize - Hubs

## Description
Dans le projet Scanorhize, les Hubs sont les boîtiers qui contrôlent les scanners et qui transmettent les images à la plateforme Web.<br/>
Ils sont composés d'un Raspberry Pi, d'une une carte Witty Pi pour l'horloge temps réel, d'une carte relais et d'une carte Big 7 pour avoir des ports USB additionnels.<br/>
La contrainte essentielle des Hubs est la gestion de l'alimentation qui doit être minimale afin qu'ils puissent fonctionner en autonomie le plus longtemps possible.<br/>
A cette fin on utilise une carte horloge temps réel, la carte Witty Pi, qui est programmée pour des réveils périodiques. Au réveil, le Raspberry démarre, sans alimenter aucun port USB des scanners ni de la clé 4G pour la communication Internet.<br/>
Le Raspberry va faire ses acquisition en allumant les scanners un par un grâce à la carte relai. Une fois les acquisitions terminées, le Raspberry allume la clé 4G pour envoyer des données et récupérer certains éléments selon la configuration du Hub.


## Premiers pas
La première étape consiste à mettre le Hub en mode configuration afin de contrôler ou modifier son paramétrage. Lorsque le Hub est éteint, il faut appuyer sur le bouton qui se trouve près des connecteurs USB, pour démarrer le Hub en mode configuration.<br/>
Le Hub va essayer de détecter les scanners qui sont branchés sur ses ports USB, puis va lancer une application Web pour sa configuration. Cette application est accessible par le Wifi "Scanorhize" sur l'Url: http://192.168.1.42:8080/ <br/>
Saisir les périodes de réveils pour chacun des scanners, enregistrer les configurations sur le serveur.<br/>
Une fois tous les paramètres saisis, les scanners et le Hub en place, on peut aller sur le menu "Hub", pour lancer une acquisition afin de s'assurer que tout fonctionne bien.<br/>
Enfin, il faut éteindre le Hub afin de préserver la batterie. Cliquer sur le bouton rouge "Power off". On ne doit plus voir aucune led allumée sur le Hub après quelques secondes.<br/>
Par la suite, le Hub va se réveiller selon sa programmation, faire des acquisitions et envoyer ses données au serveur.


## Détail du fonctionnement
Au démarrage du Raspberry, on lance la commande `/home/pi/Scanorhize/StartScanorhize.sh`<br/>
Ce shell lance ScanorhizeStart.py qui gère les heures de réveil et d'endormissement du Hub et qui selon le mode de démarrage (appui sur le bouton ON/OFF ou réveil programmé) va lancer l'acquisition des images par le scanner ou le serveur Web en mode configuration.<br/>
Le serveur Flask est lancé par la commande Scanorhize.py et l'acquisition par ScanorhizeProcess.py


#### Mode Configuration
Le fait d'allumer le boîtier avec le bouton ON/OFF active le mode configuration automatiquement. On détecte au démarrage du Raspberry qu'il a été allumé par appui sur le bouton d'allumage de la carte Witty Pi.<br/>
En mode configuration, le relai de chaque scanner s'allume afin de détecter les scanners branchés sur le Hub. En dernier lieu, c'est le relai de la clé 4G qui s'allume.

> [!WARNING]
> Lorsqu'on lance le mode configuration le boîtier s'arrête au bout de 20 minutes par sécurité (sinon il ne s'arrêterait pas et viderait la batterie)
> Il est recommandé de l'arrêter avant par l'interface Web, avec le bouton "Poweroff", ou avec le bouton ON/OFF du boîtier.

#### Mode nominal (acquisitions)
Le mode nominal réveille le Hub pour faire les acquisitions puis éteint le boîtier jusqu'au prochain réveil programmé.

#### Démarrage / Arrêt du boîtier
On utilise donc un bouton qui agit sur GPIO-7 (pin physique 7) avec mise à la terre, pour faire les arrêts/relances, sans jamais couper l'alimentation. Ce qui peut conduire dans certains cas à des difficultés à éteindre ou allumer le boîtier.

> [!TIP]
> Quand la pression sur le bouton poussoir ne produit aucun effet, il faut presser le bouton pendant au moins 10 secondes pour forcer l'arrêt ou le démarrage.


## Installation du logiciel
L'installation d'un Hub se fait par Ansible.<br/>
Cette méthode permet de faire évoluer les composants, les configurations et assure la répétabilité du processus.<br/>
Ansible permet également la mise à jour d'un Hub sans recopier toute la carte SD. On conserve ainsi la configuration des scanners et les logs tout en faisant évoluer le système.
A la base, on part d'une image Debian Bookworm (raspios-bookworm-armhf-lite) sur la SD Card du Raspberry, en 32 bits pour les drivers Epson.


## Configuration matérielle

### Composants matériels
Les programmes gèrent différentes configurations matérielles parmi les suivantes:
- Raspberry Pi 4 ou Pi 5 en Debian 12 32 bits pour les drivers Epson ou 64 bits si on n'utilise que des scanners Canon
- Carte RTC WittyPi 3, 4 ou 4L3V7
- carte d'extension de ports USB UUGEAR Big 7
- Carte relai RPi Relay Board ou SBComponent PiRelay-V2

Lorsqu'un Hub est endormi, sa consommation est de l'ordre de 1mA (c'est la consommation de la carte Witty Pi). Selon le modèle de carte Witty Pi on a, pour le standby mode:  
- Witty Pi 4: 0,5 mA
- Witty Pi 4 L3V7: 0,3 mA
On obtient ces valeurs quand seule la batterie est branchée. Si on est sur l'alimentation 5V (powerbank ou alimentation externe) on passe à 1mA 

> [!NOTE]
> Le Raspberry Pi 5 a dispose d'une horloge temps réel. On peut donc l'activer, à condition de ne pas utiliser le réveil profond (`POWER_OFF_ON_HALT=1`). Mais dans ce cas la consommation du Raspberry est de l'ordre de 1W (200mA), ce qui rédhibitoire pour notre projet.  

> [!NOTE]
> La carte UUGEAR Mega 4 dispose de 4 ports PPPS dont l'alimentation peut être gérée par le bus USB (Per-Port Power Switching). Malheureusement, pour que le driver de la carte fonctionne, il faut que les ports soient allumés au boot du Raspberry (mode impossible à modifier selon UUGEAR). L'appel de courant au démarrage des 3 scanners et de la clé 4G est alors beaucoup trop élevé pour les batteries, donc le Raspberry ne démarre pas. 

La carte relai permet de couper l'alimentation des ports USB de la carte Big 7. Ainsi, au démarrage du Raspberry, aucun port USB de la carte Big 7 n'est alimenté. Le Raspberry démarre sans aucun périphérique, hormis sa carte SD externe, et la consommation est minimal au boot. La valeurs de consommation restent sous 2A en pic et arrivent à 0,8/0,9A pour un Raspberry Pi 4 et 0,6/0,7A pour un Raspberry Pi 5 sans charge.
Lorsqu'on active les relais 1 par 1, on ne dépasse jamais 2A en pic.


### Scanners
Les tests ont été effectués avec des scanners grand public:
- Epson Perfection V39II

- Canon LIDE 400

#### Epson Perfection V39II
Ce scanner fonctionne bien avec les Hub, même avec une ligne USB de 5m.
Il n'a pas besoin de timeout après la mise sous tension pour effectuer un scan (2s d'attente dans l'application) ni après le scan pour couper l'alimentation car le charriot revient à sa place. Les appels de courant ne dépassent pas 1A à la mise sous tension.

#### Canon LIDE 400
Ce scanner est moins bien adapté pour les Hubs, car:
- il nécessite plus de courant à la mise sous tension, il dépasse souvent 1A, ce qui empêche parfois l'allumage du Hub lorsque les batteries sont faibles.
- Avant de scanner, il faut attendre environ 30 à 40s après la mise sous tension et 5 à 10s après le scan pour couper l'alimentation afin que le charriot revienne à sa position initiale, ce qui augmente la durée des acquisitions et donc la consommation du Hub.
- Lorsqu'on branche le scanner avec un câble USB Bulgin de 5m de long, on a beaucoup d'erreurs, car la tension du port USB en bout de ligne est trop faible.


### Configuration du GPIO
Selon les composants utilisés pour le boîtier, les GPIO utilisés sont différents.

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
- Ch2Pin = 22  # Scanner2
Attention pour ces 2 pins, il faut supprimer les jumpers jaunes
et câbler GPIO 27 et 22 (board pins 13 et 15) sur les relais avec des câbles Dupont
- Ch3Pin = 27  # Scanner3
- Ch4Pin = 19  # Clé 4G
- PinArray = [13, 22, 27, 19]

#### Pour l'alimentation de la carte WittyPi L3V7
Pins BCM
- CHRG_PIN = 5  # input to detect charging status
- STDBY_PIN = 6  # input to detect standby status
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

Il existe 2 modes de fonctionnement sur les Hubs :
- le mode configuration
- le mode nominal

### Mode configuration

Pour activer le mode configuration il faut appuyer sur le bouton lorsque le Hub est éteint.

#### Interface Web
Le mode configuration permet de configurer le Hub directement à travers une interface Web.
Pour se connecter au Raspberry quand il est en  mode configuration, il faut se connecter à son Wifi: Scanorhize.
On accède à l'interface d'Administration locale du Hub par l'URL:<br>
http://192.168.1.42:8080

#### Accès SSH
On peut aussi accéder au Raspberry depuis le serveur `backend-prod.humeos.com` si on connaît le port utilisé par le Raspberry. Le port est affiché sur l'interface Web en haut à droite dans toutes les pages. Si on n'a pas accès à l'interface Web, on peut découvrir le port avec la commande suivante sur le serveur `backend-prod.humeos.com`:
```
debian@d2-2-gra11:~$ sudo netstat -tanpl | grep -E ':22(2[3-9]|[3-9][0-9])'
tcp        0      0 127.0.0.1:2269          0.0.0.0:*               LISTEN      1040576/sshd: debian 
tcp6       0      0 ::1:2269                :::*                    LISTEN      1040576/sshd: debian
debian@d2-2-gra11:~$ 
```
Ici, on voit que la connexion se trouve sur le port 2269.<br/>
Pour se connecter au Raspberry, on peut lancer un SSH de la forme:
```
debian@d2-2-gra11:~$ ssh pi@localhost -p 2269
```
Les clés d'accès sont configurées sur le compte de l'utilisateur debian sur le serveur backend-prod.humeos.com et permettent d’accéder au Hub sans mot de passe.
Par ailleurs, comme les clés des Raspberry Pi sont différentes, afin d'éviter le message d'alerte du "Man in the middle", on ignore volontairement leurs clés avec le fichier de configuration du client SSH:
```
debian@d2-2-gra11:~$ cat .ssh/config 
# Pour accéder aux Hubs
Host localhost
    StrictHostKeyChecking No
    user pi
debian@d2-2-gra11:~$ 
```


#### Modification des configurations sur le bucket S3
Selon le mode `Use Server`, les Hubs et les scanners vont chercher leur configuration sur le bucket S3. On peut ainsi modifier les configurations sans passer en mode configuration, donc sans toucher les boîtiers.

Pour chaque Hub, on trouve les configurations sur le bucket `s3://hubs`
```
$ s3cmd ls s3://hubs/hub-2ccf67a4e3c1/home/pi/Scanorhize/ConfigFile/
2025-09-15 09:32          683  s3://hubs/hub-2ccf67a4e3c1/home/pi/Scanorhize/ConfigFile/Hub.json
2025-09-11 21:14          734  s3://hubs/hub-2ccf67a4e3c1/home/pi/Scanorhize/ConfigFile/Scanner-1.json
2025-09-05 14:49          528  s3://hubs/hub-2ccf67a4e3c1/home/pi/Scanorhize/ConfigFile/Scanner-2.json
2025-09-10 16:14          782  s3://hubs/hub-2ccf67a4e3c1/home/pi/Scanorhize/ConfigFile/Scanner-3.json
$
```

### Mode nominal
En mode nominal, le Hub se réveille, lance les acquisitions une par une, allume sa clé 4G, envoie son état, envoie ses images, supprime ses images localement, met à jour son prochain réveil et s'endort.<br/>

### A propos des résolutions et des tailles d'images
Les résolutions possible avec le Hub, sont 300, 600, 1200, 2400.  
La résolution 4800 n'a pas été retenue car produisant des images trop lourdes.  
En 2400 dpi, une image au format TIFF pèse 1,6Go, l'image au format JP2 avec une compression de facteur 10 pèse 160Mo.  
Il n'est pas possible en pratique de transférer de tels fichiers avec une clé 4G.  
Au delà de 600 dpi,le mode de fonctionnement recommandé et de stocker les JP2 sur la SD Card USB et d'envoyer les vignettes pour avoir un retour sur le fonctionnement du système.  
A noter que l'image TIFF est stockée dans un RAM disque de 2Go, d'où l'impossibilité d'utiliser la résolution 4800 dpi qui ne pourrait pas y être stockée. La conversion TIFF vers JP2 est effectuée dans le RAM disque par gdal_translate. La vignette est créé à partir du JP2.  
Une fois le fichier JP2 obtenu, il est copié avec sa vignette dans la SD Card USB.

Tableau indiquant le nombre d'images qu'on peut stocker selon la résolution et l'espace de stockage disponible.  
10Go correspondent à l'espace de stockage d'un Hub qui n'a pas de stockage externe sur le port USB.

| Résolution  | TIFF    | JP2    | Nb images 10Go | Nb images SD 64Go | Nb images SD 128Go |
|   ---------:| -------:|-------:|-------------:|---------:|------:|
| 300         | 26 Mo   | 2,6 Mo |    3900      |   25000  | 50000 |
| 600         | 100 Mo  | 10 Mo  |    1000      |    6500  | 13000 |
| 1200        | 400 Mo  | 40 Mo  |     250      |    1600  |  3200 |
| 2400        | 1,6 Go  | 160 Mo |      64      |     400  |   800 |



### A propos des clés USB 4G/Wifi
Ces clés permettent au Hub de communiquer avec la plateforme Web.
Il y a plusieurs modes de fonctionnement.

1. Fonctionnement historique.  
La clé 4G/Wifi est connectée sur un USB qui ne fait que l'alimentation 5V (pas de data). La clé sert de point d'accès (AP) pour le hub, comme pour les utilisateurs qui veulent aller sur l'application Web de configuration du Hub.  
En mode nominal, le Hub se connecte au Wifi de la clé, et obtient ainsi la connectivité Internet.
Le mode historique permet de n'avoir qu'un seul mode réseau sur le Hub, l'utilisation de l'interface wlan0 qui passe par le Wifi Scanorhize.


1. Fonctionnement actuel.  
On utilise un câble USB avec les fils data pour connecter la clé. La clé crée 2 connexions: usb0 (eth1 sur Pi 4) et wlan0  
usb0 contient une IP fournie par la clé dans le même subnet que wlan0 pour la Wifi. Néanmoins les métriques des 2 interfaces sont différentes et la priorité est donnée à usb0. Dans ce mode, le Hub utilise le port USB pour communiquer avec l'Internet, ce qui est beaucoup plus efficace que de passer par le Wifi de la clé.  
Comme les 2 interfaces du hub sont dans le même subnet, on ne voit pas le hub à travers le Wifi. On ne peut donc pas configurer le Hub à travers son interface Web par le Wifi.  
Afin de contourner ce problème, en mode configuration on désactive l'interface USB. Le Hub communique ainsi à travers le Wifi. C'est bien l'objectif souhaité.  
Sauf ce certaines clés Wifi/4G, et en particulier la clé Zunate LTE 4G (à base de Qualcomm), ne font pas "switch" entre les équipements qui y sont connectés !  
Donc il n'y a pas de communication entre le Hub et un téléphone mobile qui seraient sur le même Wifi Scanorhize !  
On ne peut donc pas configurer le Hub dans l'état à partir d'un téléphone.  
La solution mise en place est que le Hub fasse un "nmap" pour découvrir les équipements connectés et en particulier les téléphones et les ordinateur, puis qu'il lance un ping sur ces IP afin de fournir ses informations ARP. Le téléphone connaît ainsi l'adresse ARP et l'IP du Hub et peut donc communiquer avec lui !  
Le programme `/usr/local/bin/scanorhize-watch.sh` est chargé de balayer la plage `192.168.1.0/24` et de faire les ping sur les IP alive.

1. Fonctionnement futur.  
On pourrait très bien n'utiliser que des clé 4G sans Wifi, c'est typiquement le fonctionnement des cartes LTE avec antennes pour Raspberry, comme la carte Clipper HAT Mini (LTE 4G pour Raspberry Pi PIM717), qui ne fait que de la 4G.  
Dans ce cas, on activerait l'AP du Raspberry en mode configuration uniquement.  
Ca permet de limiter la consommation et d'autre part, on élimine le passage du Hub par le Wifi de la clé et enfin, on peut supposer que ces cartes ont de meilleurs performances sur la 4G.

1. Les différentes clés testées

| Modèle      | idVendor | idProduct | usb0           | wlan0        | Libellé   | Remarques |
|:--------    |:-------- |:--------  |:----           |:-----        |:--------  |:----      |
| ZTE         | 19d2     | 1225      |                | 192.168.1.XX | ZTE WCDMA Technologies MSM ZTE Mobile Broadband  |       |
| Zunate      | 05c6     | 90b3      | 192.168.1.XXX  | 192.168.1.42 |   |  Puce Qualcomm. Comme les 2 interfaces ont une IP dans le subnet 192.168.1.0/24 on éteint la liaison usb0 en mode configuration |
| Zunate      | 05c6     | 9092      | 192.168.1.XXX  | 192.168.1.42 | Qualcomm, Inc. Nokia 8110 4G |   |
| KuWfi       | 0e8d     | 2008      | 192.168.42.XXX | 192.168.1.42 | Puce ZTE. On laisse usb0 dont la métrique est prioritaire pour l'accès Internet |   |
| KuWfi       | 19d2     | 1557      | 192.168.42.XXX | 192.168.1.42 | ZTE WCDMA Technologies MSM ZXIC Mobile Boardband |   |
| KuWfi       | 19d2     | 1225      | 192.168.42.XXX | 192.168.1.42 | ZTE WCDMA Technologies MSM ZXIC Mobile Boardband |   |
| KuWfi 2020  | 0e8d     | 2002      |                | 192.168.1.XX | MediaTek Inc. uf906_35_lowram_20200827 | Clé obsolète dont les débits ne dépassent pas 10Mbps    |



## Problèmes et Diagnostics

### On ne reçoit plus d'images du Hub
Les causes les plus courantes sont :
- La batterie est trop faible pour démarrer le Hub
- La communication par la clé 4G est mauvaise
- L'abonnement de la carte SIM est épuisé, il n'y plus de data. Il faut éviter ce cas, car, la communication peut rester bloquée lors d'un transfert et vider la batterie pendant les timeouts.
- Le programme d'acquisition a planté, laissant le Hub réveillé jusqu'à l'endormissement de secours qui a lieu au bout de 20 minutes

### Diagnostics

#### Les leds
- Lorsque le bloc de batteries est en charge par la powerbank, la led bleue s'allume de manière fixe sur la carte Witty Pi
- Lorsque la led bleue de la carte Witty Pi clignote, c'est que la batterie est déconnectée
- Lorsque la led verte de la carte Witty Pi est allumée, c'est que le 5V est branché (powerbank ou alimentation externe)
- La diode blanche à coté du bouton de la carte Witty Pi, clignote lorsque le Hub est endormi.
- Lorsque le Hub est réveillé, on voit des led rouges sur les cartes Relais, Raspberry et Big 7. La led verte sur le Raspberry indique les lectures/écritures sur le stockage.
- La led de la clé 4G est verte lorsqu'elle est connectée à l'Internet
- Si les voyants du Hub restent rouges mais qu'il ne se passe rien ou que le Hub s'éteint quelques secondes après l'allumage, c'est qu'il n'a plus assez de batterie. Pour forcer l'extinction du Hub, appuyer sur le bouton plus de 10 secondes.
- Si on ne voit que les 3 leds rouges d'alimentation, c'est que le Hub est sous tension mais que le Raspberry ne fonctionne pas ou qu'il est planté par un arrêt du programme. S'il ne répond pas sur le réseau, il faut forcer l'arrêt en appuyant plus de 10 s sur le bouton.  
Si le Hub répond sur le réseau, il faut regarder la log Log/ScanorhizeStart.log qui doit détailler l'incident.
- Si on voit les leds rouges et la led verte fixes dans les 10 secondes suivant le démarrage, c'est probablement un kernel panic.

#### La connectivité
- Les clés 4G sont moins performantes qu'un téléphone mobile. Ce n'est pas parce qu'on capte bien dans une zone que le Hub va bien fonctionner. Il faut tester ou mieux aller sur l'interface de la clé 4G. On peut se connecter sur le Wifi Scanorhize et voir la configuration de la clé 4G sur l'URL: http://192.168.1.1/ On voit l'état de la 4G en haut de la page à droite, une fois authentifié.
- On peut retrouver les matériels connectés et le Hub en particulier, avec des outils réseau une fois qu'on est connecté au Wifi Scanorhize. Si on a un terminal (Linux/Mac) on peut lancer:  
`$ nmap -sn 192.168.1.0/24`  
ou mieux, si on a un accès sudo:  
`$ sudo nmap -sP 192.168.1.0/24`  
qui affiche des informations supplémentaires comme le propriétaire de la MAC Address. A noter que pour le Raspberry ci dessous, la MAC Address Wifi (wlan0) est égale à la MAC Address eth0 + 1. Dans le cas ce dessous, le nom du Hub serait: `hub-2ccf676a4d5f`
```
Nmap scan report for 192.168.1.42
Host is up (3.31s latency).
MAC Address: 2C:CF:67:6A:4D:60 (Raspberry Pi (Trading))
```
- Un autre outil, sur les mobiles Android permet d'avoir les matériels connectés: Network Scanner

#### La synchronisation d'un Hub
Si on débranche la batterie et l'alimentation d'un Hub, il perd l'heure. Lorsque la désynchronisation est importante l'utilitaire s3cmd refuse de fonctionner. On ne peut donc par recevoir les images.  
Il faut absolument avoir un Hub synchronisé pour que les programmes fonctionnent.  
La seule manière pour qu'un Hub se synchronise est qu'il puisse se connecter à Internet. Lorsqu'on met le Hub en mode configuration et qu'il y a de la connectivité, il va se synchroniser avec la commande `/usr/local/bin/network-timesync.sh`. En fait cette commande est lancée par NetworkManager lorsqu'une interface réseau se met à l'état "up".



## Contribuer

## Licence

## Crédits

# Tests
