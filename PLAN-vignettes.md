# Plan: Ajout de vignettes pour les images scannées

## Objectif

Générer automatiquement des vignettes JPEG lors de chaque acquisition et permettre un mode où seules les vignettes sont envoyées au serveur (pour les hautes résolutions 600dpi+).

## Modifications à effectuer

### 1. Configuration - Paramètres des vignettes

**Fichier: `ConfigApp.py`**
- Ajouter les attributs `th_x` (512 par défaut) et `th_y` (704 par défaut) dans la classe `ConfigApp`
- Créer les fonctions getter `getThumbWidth()` et `getThumbHeight()`

### 2. Configuration Hub - Mode vignettes uniquement  

**Fichier: `Hub.py` - Classe `HubData`**
- Ajouter l'attribut `send_thumbnails_only` (booléen, défaut: False)
- Créer une fonction getter `getSendThumbnailsOnly()` pour y accéder globalement

### 3. Génération des vignettes

**Fichier: `Scanner.py`**

Créer une nouvelle fonction `generateThumbnail(jp2_path: str, thumb_path: str, original_width: float, original_height: float, th_x: int, th_y: int) -> int`
- Calculer les nouvelles dimensions en préservant le ratio d'aspect pour rentrer dans la boîte th_x × th_y:
  ```python
  ratio_image = original_width / original_height
  ratio_box = th_x / th_y
  
  if ratio_image > ratio_box:
      # Image plus large que la boîte, limitée par la largeur
      new_width = th_x
      new_height = int(original_height * th_x / original_width)
  else:
      # Image plus haute que la boîte, limitée par la hauteur
      new_height = th_y
      new_width = int(original_width * th_y / original_height)
  ```
- Utiliser `gdal_translate` pour convertir JP2 en JPEG avec les dimensions calculées
- Commande: `gdal_translate -of JPEG -outsize {new_width} {new_height} -co QUALITY=85 {jp2_path} {thumb_path}`
- Retourner 0 si succès, code erreur sinon
- Gestion d'erreur: si GDAL échoue, logger l'erreur mais ne pas bloquer l'acquisition

Modifier `scanAcq()` pour générer la vignette après la conversion JP2:
- Calculer le nom du fichier vignette basé sur `LastImgTime` avec suffixe `_thumb.jpg`
- Exemple: `image_2025-09-04T15-05-24Z_thumb.jpg` dans `getImageDir()`
- Appeler `generateThumbnail()` avec:
  - Le fichier JP2 qui vient d'être créé (`imagepathjp2000`)
  - Les dimensions de l'image (`scanner.x`, `scanner.y`)
  - Les dimensions max de la vignette (via `getThumbWidth()`, `getThumbHeight()`)
- Stocker le chemin de la vignette dans `scanner.LastThumbFile`

### 4. Copie des vignettes

**Fichier: `Campaign.py`**

Modifier `CopyImageToUSB()` pour copier également la vignette:
- Copier l'image JP2 et le JSON (comportement actuel)
- Copier aussi la vignette si elle existe: `image_{fileName}_thumb.jpg`
- Vérifier l'existence du fichier vignette avant copie
- Les vignettes sont stockées au même endroit que les images principales

### 5. Envoi sélectif au serveur

**Fichier: `Hub.py`**

Modifier `syncImageFiles()` pour gérer le mode vignettes uniquement:
- Lire la configuration Hub pour vérifier `send_thumbnails_only`
- Si `send_thumbnails_only=True`: utiliser `--include '*thumb*' --exclude '*'` pour n'envoyer que les vignettes (pas de JP2, pas de JSON)
  - Les JSON restent avec leurs JP2 sur USB pour maintenir la cohérence des données (chaque image avec sa description)
- Si `send_thumbnails_only=False`: envoyer tous les fichiers (comportement actuel)
- Commande avec inclusion sélective: 
  ```bash
  s3cmd --include '*thumb*' --exclude '*' --no-preserve --no-progress sync {src} {dest}
  ```
- Note: L'ordre des options est important dans s3cmd, les includes doivent venir avant les excludes
- Raison du filtre par nom plutôt que par extension: permet de distinguer les vignettes même si le format des images principales change de JP2 à JPEG à l'avenir

### 6. Interface Web - Logique automatique

**Fichier: `Scanorhize.py`**

Modifier `AppPage()`:
- Ajouter `th_x` et `th_y` au contexte du template (lus depuis ConfigApp)
- Les valeurs proviennent de `config.th_x` et `config.th_y`

Modifier `update_app_config()`:
- Traiter les paramètres `th_x` et `th_y` depuis le formulaire
- Valider que ce sont des entiers positifs (> 0)
- Mettre à jour `config.th_x` et `config.th_y`
- Sauvegarder dans la configuration

Modifier `process_hub_form_data()`:
- Traiter le paramètre `send_thumbnails_only` depuis le formulaire Hub (checkbox)

Modifier `HubPage()`:
- Lire les configurations de tous les scanners actifs
- Si au moins un scanner a une résolution >= 600 dpi, ajouter `auto_check_thumbnails_only=True` au contexte du template
- L'utilisateur peut toujours cocher/décocher manuellement selon ses besoins

**Fichier: `templates/App.html`**

Ajouter deux champs pour les dimensions des vignettes :
- `th_x` : "Thumbnail width (pixels)" - largeur maximale de la vignette
- `th_y` : "Thumbnail height (pixels)" - hauteur maximale de la vignette
- Valeurs affichées : `{{app_config.th_x}}` et `{{app_config.th_y}}` (provenant de ConfigApp)
- Valeurs par défaut dans ConfigApp.py : 512 et 704

**Fichier: `templates/Hub.html`**

Ajouter une checkbox "Send thumbnails only":
- Label: "Send thumbnails only"
- Utiliser la variable `auto_check_thumbnails_only` pour cocher automatiquement si résolution >= 600 dpi
- Ajouter un tooltip expliquant: "Send only thumbnails to server, JP2 and JSON remain on USB (recommended for resolutions >= 600dpi)"
- Ajouter un badge info si auto-coché: "Auto-enabled (resolution >= 600 dpi)"

### 7. Gestion des erreurs

- Ajouter la gestion d'erreur dans `generateThumbnail()` avec logging approprié (respect des règles: pas de f-string avec getLogger, exceptions explicites)
- Ne pas bloquer l'acquisition si la génération de vignette échoue (warning seulement)
- Logger les erreurs mais continuer le processus d'acquisition normal

## Fichiers impactés

- `ConfigApp.py` - Paramètres th_x, th_y
- `Hub.py` - Nouveau champ send_thumbnails_only, envoi sélectif
- `Scanner.py` - Génération vignettes, nouveau champ LastThumbFile
- `Campaign.py` - Copie vignettes
- `Scanorhize.py` - Traitement formulaires App et Hub + logique auto-check
- `templates/App.html` - Interface pour configurer th_x et th_y
- `templates/Hub.html` - Interface utilisateur avec checkbox send_thumbnails_only auto-cochée

## Compatibilité

- Les vignettes sont toujours générées lors des acquisitions
- Les vignettes sont toujours copiées sur le stockage USB avec les JP2 et JSON
- Si `send_thumbnails_only=False` (défaut): envoi de tous les fichiers (JP2, JSON, vignettes)
- Si `send_thumbnails_only=True`: envoi uniquement des vignettes
  - Les JP2 et JSON restent ensemble sur USB pour maintenir l'intégrité des données
  - Chaque image JP2 reste associée à son fichier JSON descriptif

## Use cases

1. **Résolution normale (< 600 dpi)**: 
   - Vignettes générées et copiées sur USB
   - JP2, JSON et vignettes envoyés au serveur
   - `send_thumbnails_only` non coché par défaut

2. **Haute résolution (>= 600 dpi)**:
   - Vignettes générées et copiées sur USB
   - Uniquement les vignettes envoyées au serveur (JP2 et JSON restent sur USB)
   - `send_thumbnails_only` coché automatiquement
   - Les JP2 et JSON peuvent être récupérés manuellement depuis la clé USB

3. **Mode manuel**:
   - L'utilisateur peut activer `send_thumbnails_only` même avec des résolutions faibles
   - Utile pour économiser la bande passante ou tester le système
   - Les fichiers complets restent sur USB pour récupération ultérieure

## To-dos

- [ ] Ajouter th_x et th_y dans ConfigApp.py avec fonctions getter
- [ ] Ajouter champs th_x et th_y dans App.html et traitement dans update_app_config()
- [ ] Ajouter send_thumbnails_only dans HubData avec fonction getter
- [ ] Créer fonction generateThumbnail() dans Scanner.py avec calcul du ratio
- [ ] Modifier scanAcq() pour générer vignettes automatiquement
- [ ] Modifier CopyImageToUSB() pour copier les vignettes
- [ ] Modifier syncImageFiles() pour mode vignettes uniquement avec filtre include/exclude
- [ ] Ajouter checkbox send_thumbnails_only dans Hub.html avec auto-check >= 600dpi et traitement formulaire Hub

