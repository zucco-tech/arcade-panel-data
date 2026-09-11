#!/usr/bin/env python3
"""
Releve, pour un jeu arcade, l'adresse RAM de son compteur de credits et les
codes de ses boutons — et range le resultat dans une base partageable.

    python3 capture-credits.py                 # sur la borne
    python3 capture-credits.py --hote 192.168.1.50   # depuis un PC du reseau

La chasse a l'adresse marche par difference : on photographie la RAM, tu
inseres une piece, on rephotographie, et on ne garde que les octets qui ont
augmente de exactement 1. Deux ou trois pieces suffisent. Un appui sur START
tranche ensuite la derniere ambiguite : le solde de credits redescend, un
total de pieces encaissees non.

Le releve des boutons ne marche que sur la borne (il lit /dev/input) ; a
distance, cette etape est simplement sautee.

Rien n'est jamais ecrase : une fiche deja presente n'est remplacee qu'apres
confirmation explicite.

Aucune dependance : uniquement la bibliotheque standard.
"""

import argparse
import glob
import json
import os
import select
import socket
import struct
import sys
import time

PORT = 55355
TIMEOUT = 0.6
PAS = 256                 # 256 octets par datagramme : reponse ~790 o, sous le MTU

EV = struct.Struct("llHHi")   # struct input_event
EV_KEY = 0x01

BASE_DEFAUT = "/recalbox/share/system/credits-arcade.json"


# --- Dialogue avec RetroArch --------------------------------------------

class Retro:
    def __init__(self, hote):
        self.hote = hote

    def commande(self, texte, timeout=TIMEOUT):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(texte.encode(), (self.hote, PORT))
            return sock.recv(65536).decode(errors="replace").strip()
        except OSError:
            return None
        finally:
            sock.close()

    def statut(self):
        """(nom du set, nom du core) ou None si aucun jeu ne tourne."""
        reponse = self.commande("GET_STATUS")
        if not reponse or "PLAYING" not in reponse:
            return None
        try:
            champs = reponse.split(None, 2)[2].split(",")
            return champs[1].strip(), champs[0].strip()
        except IndexError:
            return None

    def lire(self, adresse, n):
        """n octets de RAM, ou None si la zone n'est pas lisible."""
        reponse = self.commande("READ_CORE_RAM %x %d" % (adresse, n))
        if not reponse:
            return None
        parties = reponse.split()
        if len(parties) < 3 or parties[2] == "-1":
            return None
        try:
            return bytes(int(x, 16) for x in parties[2:])
        except ValueError:
            return None

    def taille_ram(self):
        """Derniere adresse lisible, trouvee par dichotomie."""
        if self.lire(0, 1) is None:
            return 0
        bas, haut = 0, 1
        while haut < (1 << 30) and self.lire(haut, 1) is not None:
            bas, haut = haut, haut << 1
        while haut - bas > 1:
            milieu = (bas + haut) // 2
            if self.lire(milieu, 1) is not None:
                bas = milieu
            else:
                haut = milieu
        return bas + 1

    def photo(self, taille):
        """Copie complete de la RAM exposee."""
        out = bytearray()
        for a in range(0, taille, PAS):
            n = min(PAS, taille - a)
            bloc = None
            for _ in range(3):        # UDP : une perte n'est pas une panne
                bloc = self.lire(a, n)
                if bloc is not None and len(bloc) == n:
                    break
            if bloc is None or len(bloc) != n:
                raise SystemExit("lecture impossible a 0x%X" % a)
            out += bloc
            if a % (PAS * 32) == 0:
                print("\r  lecture %d %%" % (100 * a // taille), end="", flush=True)
        print("\r  lecture 100 %")
        return bytes(out)


# --- Chasse a l'adresse --------------------------------------------------

def attendre(message):
    try:
        input(message + " puis [Entree] ")
    except EOFError:
        raise SystemExit("\ninterrompu")


def chasser(retro, taille):
    """Renvoie (adresse, miroirs) ou (None, []) si la chasse echoue."""
    print("\nPlace le jeu sur son ecran d'attente, sans credit.")
    attendre("Pret ?")
    avant = retro.photo(taille)

    candidats = None
    for tour in range(1, 6):
        attendre("Insere UNE piece,")
        apres = retro.photo(taille)

        # Un compteur de credits monte d'exactement 1 par piece. Le masque
        # 0xFF gere le repli a zero, la borne 0x99 ecarte les octets qui
        # comptent tout autre chose (timers, animation d'attract).
        trouves = [a for a in range(taille)
                   if apres[a] == (avant[a] + 1) & 0xFF and avant[a] < 0x99]
        candidats = trouves if candidats is None else [a for a in trouves
                                                       if a in set(candidats)]
        avant = apres
        print("  %d candidat(s) apres %d piece(s)" % (len(candidats), tour))
        if not candidats:
            print("\nAucun candidat. Le compteur est peut-etre code en BCD,")
            print("sur deux octets, ou hors de la zone lisible.")
            return None, []
        if len(candidats) <= 4:
            break

    for a in candidats:
        print("  0x%04X" % a)

    # Un solde de credits redescend quand on en consomme un ; un total de
    # pieces encaissees, non. C'est ce qui les distingue.
    valeurs = {a: avant[a] for a in candidats}
    attendre("Appuie sur START (joueur 1),")
    baisse = []
    for a in candidats:
        octet = retro.lire(a, 1)
        if octet is None:
            continue
        print("  0x%04X : %d -> %d" % (a, valeurs[a], octet[0]))
        if octet[0] < valeurs[a]:
            baisse.append(a)

    if not baisse:
        print("\nAucun candidat n'a baisse : ce sont des compteurs de pieces")
        print("encaissees, pas le solde. La fiche n'est pas concluante.")
        return None, []

    return baisse[0], baisse[1:]


# --- Releve des boutons --------------------------------------------------

def pads():
    """Les pads AllInOne, par leur nom : les numeros d'event bougent."""
    trouves = {}
    for base in sorted(glob.glob("/sys/class/input/event*")):
        try:
            with open(os.path.join(base, "device", "name")) as fh:
                nom = fh.read().strip()
        except OSError:
            continue
        if nom.startswith("AllInOne"):
            trouves[nom] = "/dev/input/" + os.path.basename(base)
    return trouves


def attendre_bouton(chemins, delai=15.0):
    """Premier code de touche enfoncee. (nom du pad, code) ou None."""
    fds = {}
    for nom, chemin in chemins.items():
        try:
            fds[os.open(chemin, os.O_RDONLY | os.O_NONBLOCK)] = nom
        except OSError as err:
            print("  %s illisible : %s" % (chemin, err))
    if not fds:
        return None
    fin = time.time() + delai
    try:
        while time.time() < fin:
            prets, _, _ = select.select(list(fds), [], [], 0.4)
            for fd in prets:
                try:
                    donnees = os.read(fd, EV.size * 64)
                except OSError:
                    continue
                for _, _, typ, code, val in EV.iter_unpack(
                        donnees[:len(donnees) // EV.size * EV.size]):
                    if typ == EV_KEY and val == 1:
                        return fds[fd], code
    finally:
        for fd in fds:
            os.close(fd)
    return None


def relever_boutons():
    """Codes des boutons piece et start, par pad. {} si pas sur la borne."""
    chemins = pads()
    if not chemins:
        print("\nPas de pad AllInOne visible : releve des boutons saute.")
        print("(normal si tu lances ce script depuis un PC)")
        return {}

    print("\nPads detectes : %s" % ", ".join(sorted(chemins)))
    releve = {}
    for libelle in ("piece", "start"):
        for nom in sorted(chemins):
            print("  appuie sur %s du pad %s..." % (libelle.upper(), nom))
            resultat = attendre_bouton({nom: chemins[nom]})
            if resultat is None:
                print("    rien recu, on passe")
                continue
            _, code = resultat
            releve.setdefault(nom, {})[libelle] = code
            print("    code %d" % code)
    return releve


# --- Base ----------------------------------------------------------------

SCHEMA = 3


def base_neuve():
    """Squelette documente : le fichier doit se comprendre sans ce script."""
    return {
        "format": "recalbox-arcade-credits",
        "version": SCHEMA,
        "description": (
            "Adresse RAM du compteur de credits de chaque jeu arcade, relevee "
            "sur la borne. Se lit par l'interface reseau de RetroArch : "
            "READ_CORE_RAM <adresse> 1 en UDP sur le port 55355. "
            "READ_CORE_MEMORY ne fonctionne pas avec FBNeo, qui ne publie "
            "aucune memory map."),
        "borne": {"carte": "AllInOne — digipcb.tech", "pads": []},
        "jeux": {},
        "difficiles": {},
    }


def charger(chemin):
    try:
        with open(chemin) as fh:
            return json.load(fh)
    except (IOError, OSError):
        return base_neuve()
    except ValueError as err:
        raise SystemExit("%s illisible (%s) — je n'y touche pas." % (chemin, err))


def enregistrer(chemin, base, nom, fiche, boutons, systeme="?"):
    # Meme convention que le script permanent : une fiche par systeme, car
    # le meme set sous un autre coeur n'a pas la meme disposition memoire.
    cle = "%s/%s" % (systeme, nom)
    ancienne = ((base.get("jeux", {}).get(cle) or {}).get("credits") or {})
    neuve = fiche["credits"]["adresse"]
    if ancienne.get("adresse") not in (None, neuve):
        print("\nUne fiche existe deja pour %s : 0x%04X"
              % (nom, ancienne["adresse"]))
        if input("La remplacer par 0x%04X ? [o/N] " % neuve).lower() != "o":
            print("Fiche conservee, rien n'est ecrit.")
            return
    base.setdefault("jeux", {})[cle] = fiche
    if boutons:
        base.setdefault("borne", {})["boutons_par_pad"] = boutons

    try:
        with open(chemin, "w") as fh:
            json.dump(base, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except (IOError, OSError) as err:
        print("\nEcriture impossible dans %s : %s" % (chemin, err))
        print("Voici la fiche, a coller a la main :\n")
        print(json.dumps({nom: fiche}, indent=2, sort_keys=True))
        return
    print("\nEcrit dans %s" % chemin)


# --- Programme -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--hote", default="127.0.0.1",
                        help="adresse de la borne (defaut : la machine locale)")
    parser.add_argument("--base", default=BASE_DEFAUT,
                        help="fichier de la base (defaut : %s)" % BASE_DEFAUT)
    parser.add_argument("--systeme", default="fbneo",
                        help="systeme Recalbox du jeu releve")
    parser.add_argument("--sans-boutons", action="store_true",
                        help="ne pas relever les codes des boutons")
    args = parser.parse_args()

    retro = Retro(args.hote)
    statut = retro.statut()
    if statut is None:
        raise SystemExit("Aucun jeu en cours sur %s — lance le jeu d'abord."
                         % args.hote)
    nom, core = statut
    print("Jeu : %s   core : %s" % (nom, core))

    taille = retro.taille_ram()
    if taille == 0:
        raise SystemExit("Ce core n'expose aucune RAM lisible : rien a faire.")
    print("RAM lisible : %d Ko (0x0000-0x%04X)" % (taille // 1024, taille - 1))

    adresse, miroirs = chasser(retro, taille)
    if adresse is None:
        raise SystemExit("\nRien d'exploitable, la base n'est pas modifiee.")

    print("\nAdresse des credits : 0x%04X%s" % (
        adresse, "   miroirs : " + " ".join("0x%04X" % m for m in miroirs)
        if miroirs else ""))

    boutons = {} if args.sans_boutons else relever_boutons()

    fiche = {
        "jeu": nom,
        "nom": nom,
        "systeme": args.systeme,
        "core": core,
        "ram": {"taille": taille, "commande": "READ_CORE_RAM"},
        "credits": {
            "adresse": adresse,
            "adresse_hex": "0x%04X" % adresse,
            "octets": 1,
            "miroirs": ["0x%04X" % m for m in miroirs],
            "verifie_insertion": True,
            "verifie_consommation": True,
        },
        "releve": {"le": time.strftime("%Y-%m-%d"),
                   "methode": "capture manuelle",
                   "par": "capture-credits.py"},
    }
    enregistrer(args.base, charger(args.base), nom, fiche, boutons, args.systeme)


if __name__ == "__main__":
    main()
