"""Les reglages du panneau, lus dans recalbox.conf.

Jusqu ici tout etait ecrit en tete des programmes : pour tamiser la borne
ou changer la couleur de la piece, il fallait ouvrir le code Python. Ces
reglages vivent maintenant la ou Recalbox range les siens, dans
/recalbox/share/system/recalbox.conf, sous des cles allinone.* :

    allinone.brightness=255          luminosite quand quelqu un est devant, 0 a 255
    allinone.brightness.idle=128     luminosite en veille, pendant les clips
    allinone.idle.delay=30           secondes sans geste avant la veille
    allinone.player2.enabled=1       0 : le poste 2 ne s allume jamais pour un jeu
    allinone.coin.color=FF0000       couleur de la PIECE qui clignote, en RGB
    allinone.blink.period=0.5        demi-periode du clignotement, en secondes
    allinone.game.idle=120           secondes sans geste ni credit : partie finie

Les valeurs ci-dessus sont celles d avant ces reglages. Une cle absente,
commentee (« ;allinone... ») ou illisible les garde : un recalbox.conf sans
section allinone donne exactement l ancienne borne. Une valeur fausse est
notee au journal, jamais fatale. Un changement est pris en compte en
quelques secondes, sans rien redemarrer — au retour au menu s il arrive
pendant une partie.

Le format est celui qu EmulationStation lit et ecrit lui-meme
(es-core/src/utils/IniFile.cpp, lu le 16/09/2026) : une ligne « cle=valeur »,
les espaces autour retires ; « # » en tete, un commentaire ; « ; » en tete,
une cle desactivee. Quand ES enregistre ses propres reglages, il relit le
fichier et ne remplace que ses lignes : les notres restent.

Le gestionnaire web ne les montre PAS : son serveur n accepte qu une liste
fixe de sections (/api/configuration/allinone repond 404, constate le
16/09/2026). On les change dans le fichier, par le partage reseau.

A importer depuis userscripts/, comme cablage :
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "system", "panneau-allinone"))
    import reglages
"""

import os
import time

RECALBOX_CONF = os.environ.get("PANNEAU_RECALBOX_CONF",
                               "/recalbox/share/system/recalbox.conf")


def _entier(mini, maxi):
    def lire(texte):
        valeur = int(texte, 10)
        if not mini <= valeur <= maxi:
            raise ValueError("hors de %d a %d" % (mini, maxi))
        return valeur
    return lire


def _duree(mini, maxi):
    def lire(texte):
        valeur = float(texte)
        if not mini <= valeur <= maxi:
            raise ValueError("hors de %g a %g" % (mini, maxi))
        return valeur
    return lire


def _booleen(texte):
    if texte in ("1", "0"):
        return texte == "1"
    raise ValueError("0 ou 1")


def _couleur(texte):
    """« FF0000 » ou « #FF0000 » : un triplet (rouge, vert, bleu)."""
    texte = texte.lstrip("#")
    if len(texte) != 6:
        raise ValueError("six chiffres hexadecimaux, comme FF0000")
    return tuple(int(texte[i:i + 2], 16) for i in (0, 2, 4))


# cle -> lecteur. Les valeurs par defaut ne sont PAS ici : ce sont les
# constantes en tete de chaque programme, celles d avant ces reglages. Un
# reglage ne les remplace que s il est ecrit, et lisible, dans le fichier —
# les bancs d essai, qui changent ces constantes, restent maitres chez eux.
CLES = {
    "allinone.brightness":       _entier(1, 255),
    "allinone.brightness.idle":  _entier(0, 255),
    "allinone.idle.delay":       _duree(1, 86400),
    "allinone.player2.enabled":  _booleen,
    "allinone.coin.color":       _couleur,
    "allinone.blink.period":     _duree(0.1, 5),
    "allinone.game.idle":        _duree(10, 86400),
}

# On ne regarde la date du fichier qu une fois par RELIRE_APRES secondes :
# les programmes tournent dix fois par seconde, un reglage n est pas si presse.
RELIRE_APRES = 2.0


def lire_conf(chemin):
    """Les cles actives du fichier, comme EmulationStation les lit."""
    cles = {}
    try:
        with open(chemin, encoding="utf-8", errors="replace") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if not ligne or ligne[0] in "#;" or "=" not in ligne:
                    continue
                cle, valeur = ligne.split("=", 1)
                cles[cle.strip()] = valeur.strip()
    except (IOError, OSError):
        pass
    return cles


class Reglages:
    """Les reglages allinone.* ecrits dans recalbox.conf, relus quand il change.

        r = Reglages(journal)
        r.get("allinone.brightness", PLEIN)   -> la valeur du fichier, sinon PLEIN
        if r.rafraichir(): ...                 vrai quand une valeur a change
    """

    def __init__(self, journal=None, chemin=None):
        self.chemin = chemin or RECALBOX_CONF
        self._journal = journal or (lambda _msg: None)
        self._date = None
        self._prochain = 0.0
        self._valeurs = {}
        self._erreurs = {}
        self.rafraichir(forcer=True)

    def get(self, cle, defaut):
        """La valeur ecrite dans le fichier, ou `defaut` si elle n y est pas."""
        return self._valeurs.get(cle, defaut)

    def _horodate(self):
        try:
            return os.path.getmtime(self.chemin)
        except OSError:
            return None

    def rafraichir(self, forcer=False):
        """Relit le fichier s il a change. Renvoie vrai si une valeur a bouge."""
        maintenant = time.monotonic()
        if not forcer and maintenant < self._prochain:
            return False
        self._prochain = maintenant + RELIRE_APRES
        date = self._horodate()
        if date == self._date:
            return False
        self._date = date
        lues = lire_conf(self.chemin)
        valeurs, erreurs = {}, {}
        for cle, lecteur in CLES.items():
            if cle not in lues:
                continue
            try:
                valeurs[cle] = lecteur(lues[cle])
            except ValueError as e:
                erreurs[cle] = "%s=%s ignore (%s)" % (cle, lues[cle], e)
        # Une erreur n est dite qu une fois, pas a chaque relecture.
        for cle, message in erreurs.items():
            if self._erreurs.get(cle) != message:
                self._journal("reglage " + message)
        self._erreurs = erreurs
        change = valeurs != self._valeurs
        if change:
            self._journal("reglages : " + (", ".join(
                "%s=%s" % (c, valeurs[c]) for c in CLES if c in valeurs) or "aucun, valeurs d origine"))
        self._valeurs = valeurs
        return change
