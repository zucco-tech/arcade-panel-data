#!/usr/bin/env python3
"""
Place une fenetre sur un ecran precis, et la met en plein ecran.

Sert a poser la fenetre du releve (un serveur X imbrique) sur le moniteur
qu on veut, une fois pour toutes. Deux demandes au gestionnaire de fenetres :

  * XMoveResizeWindow pour l amener sur le bon moniteur ;
  * un message _NET_WM_STATE_FULLSCREEN, qui est la facon normale dont une
    application reclame le plein ecran — le gestionnaire l honore et choisit
    le moniteur sur lequel la fenetre se trouve.

A ne pas confondre avec l envoi de touches par XSendEvent, essaye et rejete
par RetroArch : ici ce sont des requetes au gestionnaire de fenetres, pas des
evenements d entree simules.
"""

import ctypes
import ctypes.util
import time


# Xlib TUE le programme quand une requete porte sur une fenetre disparue —
# BadWindow, et tout s arrete. C est arrive au balayage : une capture prise
# pendant que RetroArch se fermait a fait tomber la nuit entiere au 16e jeu.
# On installe donc un gestionnaire qui avale ces erreurs : une fenetre qui
# n existe plus n est pas une raison d abandonner six mille jeux.
_GESTIONNAIRE = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)


def _ignorer(_affichage, _erreur):
    """Gestionnaire d erreurs X qui ne fait rien : une fenetre qui disparait
    pendant qu on l interroge ne doit pas tuer le programme."""
    return 0


_ignorer_c = _GESTIONNAIRE(_ignorer)


class _X:
    """Le strict necessaire de la Xlib, par ctypes : ouvrir l affichage, nommer
    un atome, parcourir l arbre des fenetres, lire un titre."""
    def __init__(self, affichage=":0"):
        self.x = ctypes.CDLL(ctypes.util.find_library("X11"))
        self.x.XSetErrorHandler.argtypes = [_GESTIONNAIRE]
        self.x.XSetErrorHandler(_ignorer_c)
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.d = self.x.XOpenDisplay(affichage.encode())
        if not self.d:
            raise OSError("affichage %s inaccessible" % affichage)
        self.x.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.racine = self.x.XDefaultRootWindow(self.d)

    def atome(self, nom):
        """Le numero d un atome X (un nom de propriete ou de message), cree s il
        n existe pas encore."""
        self.x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.x.XInternAtom.restype = ctypes.c_ulong
        return self.x.XInternAtom(self.d, nom.encode(), False)

    def enfants(self, fenetre):
        """Les fenetres filles d une fenetre, par XQueryTree ; vide si la fenetre
        n existe plus."""
        r = ctypes.c_ulong(); p = ctypes.c_ulong()
        tab = ctypes.POINTER(ctypes.c_ulong)(); n = ctypes.c_uint()
        self.x.XQueryTree.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint)]
        if not self.x.XQueryTree(self.d, fenetre, ctypes.byref(r), ctypes.byref(p),
                                 ctypes.byref(tab), ctypes.byref(n)):
            return []
        return [tab[i] for i in range(n.value)]

    def nom(self, fenetre):
        """Le titre d une fenetre (XFetchName), ou une chaine vide."""
        p = ctypes.c_char_p()
        self.x.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                      ctypes.POINTER(ctypes.c_char_p)]
        if self.x.XFetchName(self.d, fenetre, ctypes.byref(p)) and p.value:
            return p.value.decode(errors="replace")
        return ""

    def a_wm_state(self, fenetre):
        """Vrai si c est la fenetre de l APPLICATION, pas un cadre.

        Le gestionnaire de fenetres pose WM_STATE sur la fenetre cliente et
        l enveloppe dans un cadre a lui. Un message adresse au cadre est
        ignore en silence — c est ce qui faisait echouer le placement.
        """
        atome = self.atome("WM_STATE")
        typ = ctypes.c_ulong(); fmt = ctypes.c_int()
        n = ctypes.c_ulong(); reste = ctypes.c_ulong()
        donnees = ctypes.POINTER(ctypes.c_ubyte)()
        self.x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long,
            ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
        r = self.x.XGetWindowProperty(
            self.d, fenetre, atome, 0, 2, False, 0,
            ctypes.byref(typ), ctypes.byref(fmt), ctypes.byref(n),
            ctypes.byref(reste), ctypes.byref(donnees))
        return r == 0 and typ.value != 0

    def chercher(self, titre):
        """La fenetre CLIENTE dont le titre correspond."""
        def descendre(fenetre, profondeur=0):
            """Parcours en profondeur, quatre niveaux au plus : au-dela ce ne
            sont plus des fenetres d application."""
            if profondeur > 4:
                return None
            for f in self.enfants(fenetre):
                if titre.lower() in (self.nom(f) or "").lower() \
                        and self.a_wm_state(f):
                    return f
                trouve = descendre(f, profondeur + 1)
                if trouve:
                    return trouve
            return None
        trouve = descendre(self.racine)
        if trouve:
            return trouve
        # Repli : le titre sans exiger WM_STATE, mieux que rien.
        def au_titre(fenetre, profondeur=0):
            if profondeur > 4:
                return None
            for f in self.enfants(fenetre):
                if titre.lower() in (self.nom(f) or "").lower():
                    return f
                t = au_titre(f, profondeur + 1)
                if t:
                    return t
            return None
        return au_titre(self.racine)


class XEvenementClient(ctypes.Structure):
    """Un XClientMessageEvent, tel que la Xlib le range en memoire."""
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong),
                ("send_event", ctypes.c_int), ("display", ctypes.c_void_p),
                ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("donnees", ctypes.c_long * 5)]


class XEvent(ctypes.Union):
    """L union XEvent de la Xlib : assez large pour n importe quel evenement."""
    _fields_ = [("type", ctypes.c_int), ("xclient", XEvenementClient),
                ("pad", ctypes.c_long * 24)]


def _message(X, fenetre, type_message, donnees):
    """Envoie un ClientMessage au gestionnaire de fenetres ; c est ainsi qu on
    lui demande un plein ecran ou un deplacement."""
    ev = XEvent()
    ev.type = 33                                      # ClientMessage
    ev.xclient.type = 33
    ev.xclient.display = X.d
    ev.xclient.window = fenetre
    ev.xclient.message_type = X.atome(type_message)
    ev.xclient.format = 32
    for i, v in enumerate(donnees[:5]):
        ev.xclient.donnees[i] = v
    X.x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                               ctypes.c_long, ctypes.POINTER(XEvent)]
    # SubstructureRedirect | SubstructureNotify, adresse a la racine : c est
    # ainsi qu une application s adresse au gestionnaire de fenetres.
    X.x.XSendEvent(X.d, X.racine, False, (1 << 20) | (1 << 19), ctypes.byref(ev))
    X.x.XFlush(X.d)


# Deux impasses a ne pas rouvrir, constatees sous GNOME : il ignore
# _NET_WM_FULLSCREEN_MONITORS (le plein ecran retombe sur le moniteur
# principal), et il ignore les XMoveResizeWindow des fenetres qu il gere. Ce
# qui marche est ci-dessous : deplacer PUIS demander le plein ecran.
def placer(titre, x, y, largeur, hauteur, plein_ecran=True,
           affichage=":0", essais=20):
    """Amene la fenetre `titre` en (x, y) et la passe en plein ecran.

    Renvoie vrai si la fenetre a ete trouvee et deplacee.
    """
    X = _X(affichage)
    fenetre = None
    for _ in range(essais):
        fenetre = X.chercher(titre)
        if fenetre:
            break
        time.sleep(0.5)
    if not fenetre:
        return False

    X.x.XMoveResizeWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                      ctypes.c_int, ctypes.c_int,
                                      ctypes.c_uint, ctypes.c_uint]
    X.x.XMoveResizeWindow(X.d, fenetre, x, y, largeur, hauteur)
    X.x.XFlush(X.d)
    time.sleep(0.6)

    if plein_ecran:
        etat = X.atome("_NET_WM_STATE")
        plein = X.atome("_NET_WM_STATE_FULLSCREEN")
        ev = XEvent()
        ev.type = 33                                  # ClientMessage
        ev.xclient.type = 33
        ev.xclient.display = X.d
        ev.xclient.window = fenetre
        ev.xclient.message_type = etat
        ev.xclient.format = 32
        ev.xclient.donnees[0] = 1                     # _NET_WM_STATE_ADD
        ev.xclient.donnees[1] = plein
        ev.xclient.donnees[2] = 0
        ev.xclient.donnees[3] = 1                     # source : application
        X.x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                   ctypes.c_long, ctypes.POINTER(XEvent)]
        # SubstructureRedirect | SubstructureNotify, adresse a la racine :
        # c est ainsi qu une application demande le plein ecran.
        X.x.XSendEvent(X.d, X.racine, False, (1 << 20) | (1 << 19), ctypes.byref(ev))
        X.x.XFlush(X.d)
    return True


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else "releve credits"
    x, y = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (0, 1200)
    l, h = (int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (1280, 1024)
    print("placee" if placer(t, x, y, l, h) else "fenetre introuvable")
