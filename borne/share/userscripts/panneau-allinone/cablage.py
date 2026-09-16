"""Qui est qui sur le panneau : boutons, codes, roles et LED.

Le demon des credits et le panneau du menu ont besoin de la meme chose, et
ne doivent pas la deviner :

  - quel CODE envoie chaque bouton physique, et sur quelle LED il est :
    c est du cablage. Il est mesure une fois avec associer-boutons (on
    allume une LED, le joueur appuie sur le bouton allume, on note le code)
    et garde dans cablage.json. Sans ce fichier, on prend la mesure du
    14/09/2026 sur la borne de reference ;
  - quel ROLE Recalbox donne a chaque code — south, east, west, north, l1,
    r1, select, start, hotkey — et de quel TYPE est la manette : c est
    es_input.cfg, ce que l on refait dans « Configurer une manette ». On
    le lit tel quel : si le joueur remappe, les LED suivent ;
  - ce que le JEU voit reellement. Recalbox ne passe pas les roles tels
    quels a l emulateur : sur un panneau d arcade a six boutons
    (gamepadtype « arcade6 »), son configgen REORDONNE les boutons pour
    que la rangee du bas porte les coups de pied et la rangee du haut les
    poings — sauf pour MAME, qui les prend dans l ordre. Cette regle est
    recopiee ici depuis configgen/controllers/controller.py (Recalbox 11,
    lue le 14/09/2026) et verifiee contre retroarchcustom.cfg, le fichier
    que RetroArch charge vraiment ; en jeu, c est ce fichier qui a le
    dernier mot.

De ces tables on deduit tout : la LED du bouton 1 du jeu (bouton 1 = role b
sous FBNeo ; sur ce systeme, b recoit le bouton que Recalbox appelle
north ; north = tel code ; tel code = telle LED), le code de la piece, du
start, de la hotkey. Une seule source pour les deux programmes.

Ou il vit, et pourquoi la. Le code partage par les programmes du panneau
est range dans userscripts/panneau-allinone/, a cote de ceux qui s en
servent ; les donnees (credits, cablage.json, journaux) restent dans
system/panneau-allinone/. Un SOUS-DOSSIER, pas userscripts/ lui-meme :
EmulationStation execute tout .py ou .sh pose directement dans userscripts
et dont le nom ne porte pas d evenements entre crochets — a CHAQUE evenement,
chaque mouvement dans le menu (NotificationManager.cpp, LoadScriptList et
ExtractNotificationsFromPath, lu le 16/09/2026). Les sous-dossiers, il ne
les regarde pas.

A importer depuis userscripts/ :
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "panneau-allinone"))
    import cablage
"""

import json
import os
import re
import xml.etree.ElementTree as ET

ES_INPUT = "/recalbox/share/system/.emulationstation/es_input.cfg"
RETROARCH = "/recalbox/share/system/configs/retroarch/retroarchcustom.cfg"
# Ce que RetroArch charge PAR-DESSUS retroarchcustom.cfg : la chaine des
# .retroarch.cfg des dossiers de roms, recopiee la par configgen a chaque
# lancement (configOverriding.buildOverrideChain, --appendconfig).
RETROARCH_SURCHARGE = RETROARCH + ".overrides.cfg"
# La surcharge d un systeme entier, dans son dossier de roms. C est par elle
# qu on remet FBNeo dans l ordre du dessin (outils/aligner-boutons.py) : le
# panneau doit la connaitre des le menu, avant que le jeu ne soit lance.
SURCHARGE_SYSTEME = "/recalbox/share/roms/%s/.retroarch.cfg"
# Le cablage mesure est une DONNEE de la borne : il reste dans
# system/panneau-allinone/, deux dossiers plus haut que ce module.
FICHIER_CABLAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "..", "system", "panneau-allinone", "cablage.json")
MANETTES = {1: "AllInOneP1", 2: "AllInOneP2"}

# Ce que les jeux appellent bouton 1, 2, 3... : sous FBNeo comme sous MAME
# (RetroPad classique) le bouton 1 est B, le 2 est A, le 3 est Y, le 4 est
# X, puis les gachettes. C est une convention du coeur d emulation.
ROLE_DU_BOUTON = {1: "b", 2: "a", 3: "y", 4: "x", 5: "l1", 6: "r1", 7: "l2", 8: "r2"}

# Recalbox nomme les quatre boutons de face de deux facons selon la version :
# les lettres du RetroPad (b, a, y, x) et les points cardinaux de SDL (south,
# east, west, north) — c est le meme bouton. On lit les deux, on parle en
# lettres.
LETTRE = {"south": "b", "east": "a", "west": "y", "north": "x"}
# Les noms de RetroArch pour nos roles (retroarchcustom.cfg : input_player1_l_btn).
NOM_RETROARCH = {"l1": "l", "r1": "r"}

# La mesure de reference (borne du 14/09/2026), code evdev -> numero de LED
# aio_p*_b<n>. Sert quand cablage.json manque. Les deux postes envoient les
# memes codes sur leur propre manette.
CABLAGE_DEFAUT = {304: 1, 305: 2, 307: 3, 313: 4, 311: 5, 310: 6}
# Ce que l assistant de Recalbox ecrit pour ce panneau quand on presse les
# boutons dans l ordre du dessin (1 a 6 : south, east, west, north, l1,
# r1) ; sert quand es_input.cfg manque (les bancs d essai, une borne pas
# encore configuree).
ROLES_DEFAUT = {"b": 304, "a": 305, "y": 307, "x": 313, "l1": 311, "r1": 310,
                "select": 314, "start": 315, "hotkey": 316}
TYPE_DEFAUT = "arcade6"

# --- la regle de Recalbox (configgen, controller.py et libretroControllers.py)
# Panneaux consideres comme des sticks d arcade, et ceux a six boutons.
TYPES_ARCADE = ("arcade4", "arcade6", "arcade8")
TYPES_SIX = ("arcade6", "arcade8")
# Les systemes que Recalbox laisse dans l ordre (_NO_SHUFFLE_ARCADE_SYSTEMS).
SANS_REORDRE = frozenset({"mame"})
# Sur la famille Naomi, Recalbox echange L1 et R1 pour tout stick d arcade.
NAOMI = frozenset({"naomi", "naomigd", "atomiswave"})
# Megadrive sur un stick d arcade : ses propres tables, role Recalbox ->
# nom RetroArch (retroarchmegadrivebtns / retroarchmegadrive6btns).
MEGADRIVE_3 = {"a": "b", "b": "y", "x": "x", "y": "a", "l1": "l1", "r1": "r1"}
MEGADRIVE_6 = {"a": "b", "b": "y", "x": "x", "y": "l1", "l1": "r1", "r1": "a"}
ROLES_DE_JEU = ("b", "a", "y", "x", "l1", "r1", "l2", "r2")


def _lire_es_input(chemin=ES_INPUT):
    """{nom de manette: (roles, ids, type)} d apres es_input.cfg ; {} s il
    manque. roles : role -> code evdev ; ids : numero SDL -> code, c est par
    ce numero que retroarchcustom.cfg designe un bouton."""
    try:
        racine = ET.parse(chemin).getroot()
    except (OSError, ET.ParseError):
        return {}
    manettes = {}
    for config in racine.iter("inputConfig"):
        roles, ids = {}, {}
        for entree in config.iter("input"):
            if entree.get("type") != "button":
                continue
            try:
                code = int(entree.get("code"))
            except (TypeError, ValueError):
                continue
            nom = entree.get("name")
            roles[LETTRE.get(nom, nom)] = code
            try:
                ids[int(entree.get("id"))] = code
            except (TypeError, ValueError):
                pass
        manettes[config.get("deviceName")] = (roles, ids, config.get("gamepadtype") or "standard")
    return manettes


def _lire_cablage(chemin=FICHIER_CABLAGE):
    """{poste: {code: LED}} d apres cablage.json ; {} s il manque."""
    try:
        with open(chemin) as fh:
            postes = json.load(fh).get("postes") or {}
    except (OSError, ValueError):
        return {}
    return {int(p): {int(c): int(l) for c, l in table.items()} for p, table in postes.items()}


def _lire_retroarch(*chemins):
    """{joueur: {nom RetroArch: numero SDL}} d apres les fichiers donnes, lus
    dans l ordre : un fichier plus loin l emporte, comme --appendconfig chez
    RetroArch. Un fichier absent ne compte pas ; {} si aucun ne dit rien."""
    joueurs = {}
    for chemin in chemins:
        try:
            with open(chemin) as fh:
                texte = fh.read()
        except OSError:
            continue
        for j, nom, numero in re.findall(r"^input_player(\d)_(\w+?)_btn\s*=\s*\"?(\d+)", texte, re.M):
            joueurs.setdefault(int(j), {})[nom] = int(numero)
    return joueurs


def _horodate(chemin):
    try:
        return os.path.getmtime(chemin)
    except OSError:
        return None


class Cablage:
    """Les tables d un panneau. `source` dit d ou elles viennent, pour le
    journal de demarrage.

    Elles se relisent toutes seules : es_input.cfg change chaque fois que
    quelqu un reconfigure une manette dans EmulationStation, et
    retroarchcustom.cfg a chaque lancement de jeu. Un programme qui garde
    l ancienne version eclaire les mauvais boutons — constate le
    14/09/2026. Appeler rafraichir() regulierement suffit : il ne relit que
    si un fichier a change."""

    def __init__(self, es_input=ES_INPUT, fichier_cablage=FICHIER_CABLAGE, retroarch=RETROARCH,
                 surcharge=None, surcharge_systeme=SURCHARGE_SYSTEME):
        surcharge = surcharge if surcharge is not None else retroarch + ".overrides.cfg"
        self._fichiers = (es_input, fichier_cablage, retroarch, surcharge)
        self._surcharge_systeme = surcharge_systeme
        self._systemes = {}          # systeme -> (date, surcharge lue)
        self._dates = {}
        self._charger()

    def _charger(self):
        """Lit les trois fichiers et en tire les tables ; retient leur date
        pour savoir quand relire."""
        es_input, fichier_cablage, retroarch, surcharge = self._fichiers
        es = _lire_es_input(es_input)
        physique = _lire_cablage(fichier_cablage)
        self._roles, self._ids, self._types = {}, {}, {}
        for j, nom in MANETTES.items():
            roles, ids, genre = es.get(nom) or (dict(ROLES_DEFAUT), {}, TYPE_DEFAUT)
            self._roles[j], self._ids[j], self._types[j] = roles, ids, genre
        self._led_du_code = {j: physique.get(j) or dict(CABLAGE_DEFAUT) for j in MANETTES}
        self._retroarch = _lire_retroarch(retroarch, surcharge)
        self.source = "%s, %s" % ("es_input.cfg" if es else "roles par defaut",
                                  "cablage.json" if physique else "cablage par defaut")
        self._dates = self._horodates()

    def _horodates(self):
        """La date de derniere modification de chaque fichier, None s il manque."""
        return {chemin: _horodate(chemin) for chemin in self._fichiers}

    def rafraichir(self):
        """Relit les tables si un fichier a change depuis la derniere fois.
        Renvoie vrai quand quelque chose a bouge — de quoi le noter au
        journal et repeindre le panneau."""
        if self._horodates() == self._dates:
            return False
        self._charger()
        return True

    # -- ce que Recalbox a configure

    def code(self, joueur, role):
        """Le code evdev du role tel que Recalbox l a enregistre (« select »,
        « start », « b »...), quelle que soit l ecriture des quatre boutons
        de face. C est le bouton du MENU ; en jeu, voir disposition()."""
        roles = self._roles[joueur]
        role = LETTRE.get(role, role)
        return roles.get(role)

    def role(self, joueur, code):
        """Le role Recalbox d un code sur ce poste, ou None, en lettres."""
        for r, c in self._roles[joueur].items():
            if c == code:
                return r
        return None

    def led_du_code(self, joueur, code):
        """Le numero de LED (1..8) du bouton qui envoie ce code, ou None."""
        return self._led_du_code[joueur].get(code)

    # -- ce que le jeu voit

    def surcharge_systeme(self, systeme):
        """{joueur: {nom RetroArch: numero SDL}} de la surcharge du dossier de
        roms de ce systeme, {} s il n y en a pas. Relue quand elle change : le
        dossier est sur le NAS, on ne la garde pas plus qu un tour."""
        if not systeme or not self._surcharge_systeme:
            return {}
        chemin = self._surcharge_systeme % systeme
        date = _horodate(chemin)
        connue = self._systemes.get(systeme)
        if connue is None or connue[0] != date:
            connue = (date, _lire_retroarch(chemin) if date is not None else {})
            self._systemes[systeme] = connue
        return connue[1]

    def disposition(self, joueur, systeme=""):
        """{role du jeu: code} sur ce systeme, d apres la regle de Recalbox.

        Sur un panneau a six boutons, configgen transforme

            south east west        west  north l1
            north l1   r1    en    south east  r1

        c est-a-dire : le role b du jeu recoit le bouton que Recalbox
        appelle north, a recoit l1, y recoit south, x recoit east, l1
        recoit west, r1 ne bouge pas. MAME est laisse dans l ordre ; la
        famille Naomi echange ensuite L1 et R1 ; la Megadrive a ses tables.
        Une surcharge .retroarch.cfg du dossier de roms passe par-dessus.
        Les boutons de facade (select, start, hotkey) ne bougent jamais."""
        entrees = dict(self._roles[joueur])
        genre = self._types[joueur]
        if genre in TYPES_SIX and "l1" in entrees and systeme not in SANS_REORDRE:
            b, a, y, x, l1 = (entrees.get(r) for r in ("b", "a", "y", "x", "l1"))
            entrees.update({"a": l1, "b": x, "x": a, "y": b, "l1": y})
        if genre in TYPES_ARCADE and systeme in NAOMI and "l1" in entrees and "r1" in entrees:
            entrees["l1"], entrees["r1"] = entrees["r1"], entrees["l1"]
        table = {r: r for r in ROLES_DE_JEU}
        if genre in TYPES_ARCADE and systeme == "megadrive":
            table.update(MEGADRIVE_6 if genre in TYPES_SIX else MEGADRIVE_3)
        jeu = {ra: entrees.get(role) for role, ra in table.items() if entrees.get(role) is not None}
        # Une surcharge du dossier de roms a le dernier mot, comme chez
        # RetroArch : c est elle qui remet FBNeo dans l ordre du dessin.
        for nom, numero in self.surcharge_systeme(systeme).get(joueur, {}).items():
            role = {"l": "l1", "r": "r1"}.get(nom, nom)
            if role in ROLES_DE_JEU and numero in self._ids[joueur]:
                jeu[role] = self._ids[joueur][numero]
        for facade in ("select", "start", "hotkey"):
            if facade in entrees:
                jeu[facade] = entrees[facade]
        return jeu

    def code_en_jeu(self, joueur, role):
        """Le code que RetroArch a VRAIMENT donne a ce role dans la partie en
        cours, d apres retroarchcustom.cfg, ou None si le fichier ne le dit
        pas. Ne vaut que pendant une partie : hors jeu, le fichier decrit la
        precedente."""
        numero = self._retroarch.get(joueur, {}).get(NOM_RETROARCH.get(role, role))
        return self._ids[joueur].get(numero) if numero is not None else None

    def ecart_retroarch(self, joueur, systeme=""):
        """Les roles ou RetroArch ne fait pas ce que la regle prevoit —
        vide si tout concorde ou si retroarchcustom.cfg manque. A ecrire au
        journal : c est le signe que Recalbox a change sa regle, ou qu un
        remap par jeu s applique."""
        if not self._retroarch.get(joueur) or self.surcharge_systeme(systeme):
            return []
        regle = self.disposition(joueur, systeme)
        ecarts = []
        for role in ROLES_DE_JEU[:6]:
            vrai = self.code_en_jeu(joueur, role)
            if vrai is not None and regle.get(role) != vrai:
                ecarts.append("%s : regle %s, retroarch %s" % (role, regle.get(role), vrai))
        return ecarts

    def led_du_bouton(self, joueur, numero, systeme="", en_jeu=False):
        """La LED du bouton numero N du jeu sur ce systeme, ou None :
        bouton -> role -> code -> LED. En jeu, le code vient de ce que
        RetroArch a charge ; sinon de la regle de Recalbox."""
        role = ROLE_DU_BOUTON.get(numero, "")
        # Systeme aligne par aligner-boutons.py : le bouton N du jeu est a la
        # position N, par construction — y compris pour les jeux que le coeur
        # range autrement, dont le fichier par jeu change les noms RetroPad
        # mais pas les positions. RetroArch n a donc rien a nous apprendre.
        if self.surcharge_systeme(systeme):
            en_jeu = False
        code = self.code_en_jeu(joueur, role) if en_jeu else None
        if code is None:
            code = self.disposition(joueur, systeme).get(role)
        return self.led_du_code(joueur, code) if code is not None else None

    def bouton_de_led(self, joueur, led, systeme="", en_jeu=False):
        """Le numero de bouton du jeu que porte cette LED, ou None."""
        for numero in ROLE_DU_BOUTON:
            if self.led_du_bouton(joueur, numero, systeme, en_jeu) == led:
                return numero
        return None
