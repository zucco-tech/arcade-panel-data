"""Qui est qui sur le panneau : boutons, codes, roles et LED.

Le demon des credits et le panneau du menu ont besoin de la meme chose, et
ne doivent pas la deviner :

  - quel CODE envoie chaque bouton physique, et sur quelle LED il est :
    c est du cablage. Il est mesure une fois avec associer-boutons (on
    allume une LED, le joueur appuie sur le bouton allume, on note le code)
    et garde dans cablage.json. Sans ce fichier, on prend la mesure du
    14/09/2026 sur la borne de reference ;
  - quel ROLE joue chaque code — b, a, y, x, l1, r1, select, start, hotkey :
    c est le mappage de Recalbox, es_input.cfg, celui que l on refait dans
    « Configurer une manette ». On le lit tel quel : si le joueur remappe,
    les LED suivent.

De ces deux tables on deduit tout : la LED du bouton 1 du jeu (bouton 1 =
role b sous FBNeo, b = tel code, tel code = telle LED), le code de la
piece, du start, de la hotkey. Une seule source pour les deux programmes.

A importer depuis userscripts/ :
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "system", "panneau-allinone"))
    import cablage
"""

import json
import os
import xml.etree.ElementTree as ET

ES_INPUT = "/recalbox/share/system/.emulationstation/es_input.cfg"
FICHIER_CABLAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cablage.json")
MANETTES = {1: "AllInOneP1", 2: "AllInOneP2"}

# Ce que les jeux appellent bouton 1, 2, 3... : sous FBNeo (disposition
# classique) le bouton 1 est B, le 2 est A, le 3 est Y, le 4 est X, puis
# les gachettes. C est la seule table qui ne vienne ni de Recalbox ni du
# cablage : c est une convention du coeur d emulation.
ROLE_DU_BOUTON = {1: "b", 2: "a", 3: "y", 4: "x", 5: "l1", 6: "r1", 7: "l2", 8: "r2"}

# La mesure de reference (borne du 14/09/2026), code evdev -> numero de LED
# aio_p*_b<n>. Sert quand cablage.json manque. Les deux postes envoient les
# memes codes sur leur propre manette.
CABLAGE_DEFAUT = {304: 1, 305: 2, 307: 3, 313: 4, 311: 5, 310: 6}
# Le mappage de reference de Recalbox pour cette carte, role -> code. Sert
# quand es_input.cfg manque (les bancs d essai, une borne pas encore
# configuree).
ROLES_DEFAUT = {"y": 304, "x": 305, "l1": 307, "b": 313, "a": 311, "r1": 310,
                "select": 314, "start": 315, "hotkey": 316}


def _lire_es_input(chemin=ES_INPUT):
    """{nom de manette: {role: code}} d apres es_input.cfg ; {} s il manque."""
    try:
        racine = ET.parse(chemin).getroot()
    except (OSError, ET.ParseError):
        return {}
    manettes = {}
    for config in racine.iter("inputConfig"):
        roles = {}
        for entree in config.iter("input"):
            if entree.get("type") == "button":
                try:
                    roles[entree.get("name")] = int(entree.get("code"))
                except (TypeError, ValueError):
                    pass
        manettes[config.get("deviceName")] = roles
    return manettes


def _lire_cablage(chemin=FICHIER_CABLAGE):
    """{poste: {code: LED}} d apres cablage.json ; {} s il manque."""
    try:
        with open(chemin) as fh:
            postes = json.load(fh).get("postes") or {}
    except (OSError, ValueError):
        return {}
    return {int(p): {int(c): int(l) for c, l in table.items()} for p, table in postes.items()}


class Cablage:
    """Les tables d un panneau, chargees une fois. `source` dit d ou elles
    viennent, pour le journal de demarrage."""

    def __init__(self, es_input=ES_INPUT, fichier_cablage=FICHIER_CABLAGE):
        es = _lire_es_input(es_input)
        physique = _lire_cablage(fichier_cablage)
        self._roles = {j: es.get(nom) or dict(ROLES_DEFAUT) for j, nom in MANETTES.items()}
        self._led_du_code = {j: physique.get(j) or dict(CABLAGE_DEFAUT) for j in MANETTES}
        self.source = "%s, %s" % ("es_input.cfg" if es else "roles par defaut",
                                  "cablage.json" if physique else "cablage par defaut")

    def code(self, joueur, role):
        """Le code evdev du role (« select », « start », « b »...) sur ce poste."""
        return self._roles[joueur].get(role)

    def role(self, joueur, code):
        """Le role d un code sur ce poste, ou None."""
        for r, c in self._roles[joueur].items():
            if c == code:
                return r
        return None

    def led_du_code(self, joueur, code):
        """Le numero de LED (1..8) du bouton qui envoie ce code, ou None."""
        return self._led_du_code[joueur].get(code)

    def led_du_bouton(self, joueur, numero):
        """La LED du bouton numero N du jeu, ou None : bouton -> role -> code -> LED."""
        code = self.code(joueur, ROLE_DU_BOUTON.get(numero, ""))
        return self.led_du_code(joueur, code) if code is not None else None

    def bouton_de_led(self, joueur, led):
        """Le numero de bouton du jeu que porte cette LED, ou None."""
        for numero in ROLE_DU_BOUTON:
            if self.led_du_bouton(joueur, numero) == led:
                return numero
        return None

    def est_bouton_de_jeu(self, joueur, code):
        """Vrai pour un bouton d action, faux pour piece, start, hotkey ou inconnu."""
        return self.role(joueur, code) in ROLE_DU_BOUTON.values()
