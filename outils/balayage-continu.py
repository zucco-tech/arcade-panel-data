#!/usr/bin/env python3
"""
Fait tourner le releve en continu, systeme apres systeme, sans surveillance.

    python3 balayage-continu.py

Pense pour une machine dediee qui tourne jour et nuit. Il enchaine les
systemes dans l ordre, reprend les jeux ecartes une fois le systeme fini,
puis passe au suivant. Quand tout est fait il se rendort et reverifie plus
tard : une base de cheats mise a jour, des roms ajoutees, et il reprend.

Il s arrete proprement si le fichier d arret existe, et il ne demarre jamais
sans avoir verifie le jeu temoin — relever six mille adresses avec un coeur
qui range sa memoire autrement serait du temps perdu deux fois.

Aucune dependance : uniquement la bibliotheque standard.
"""

import importlib.util
import os
import subprocess
import sys
import time

RACINE = "/mnt/recalbox"
OUTILS = os.path.join(RACINE, "outils")
BASE = os.path.join(RACINE, "donnees", "credits-arcade.json")
JOURNAUX = os.path.join(RACINE, "journaux")
ROMS = "/mnt/roms"
ARRET = "/tmp/arret-nuit"

# L ordre compte : on commence par ce qu on maitrise, on garde pour la fin
# les coeurs dont on ignore s ils exposent leur memoire.
# Pas de « fba » : systeme absent de la borne, roms jamais lancees.
SYSTEMES = ["fbneo", "neogeo", "neogeocd",
            "naomi", "naomigd", "naomi2", "atomiswave"]

# Ces systemes partagent fbneo_libretro.so : le nom observe au controle du
# temoin vaut pour eux tous, et pour eux seuls.
FAMILLE_TEMOIN = ("fbneo", "fba", "neogeo", "neogeocd")

# Le jeu temoin et son adresse, mesures a la main sur la borne avec de
# vraies pieces. Si le coeur d ici ne donne pas la meme chose, sa disposition
# memoire differe et rien de ce qu on releverait ne vaudrait ailleurs.
TEMOIN = ("fbneo", "pzloop2", 0x0450)

REPOS_ENTRE_TOURS = 900.0     # quand tout est fait, on repasse dans un quart d heure


def journal(msg):
    horodate = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(horodate, flush=True)
    try:
        os.makedirs(JOURNAUX, exist_ok=True)
        with open(os.path.join(JOURNAUX, "continu.log"), "a") as fh:
            fh.write(horodate + "\n")
    except OSError:
        pass


def arret_demande():
    return os.path.exists(ARRET)


def outil_nuit():
    """Charge nuit-credits.py comme module : son nom interdit un import."""
    chemin = os.path.join(OUTILS, "nuit-credits.py")
    spec = importlib.util.spec_from_file_location("nuit_credits", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rom_du_jeu(systeme, jeu):
    for extension in (".zip", ".7z"):
        chemin = os.path.join(ROMS, systeme, jeu + extension)
        if os.path.exists(chemin):
            return chemin
    return None


def verifier_temoin():
    """Le coeur d ici range-t-il sa memoire comme celui de la borne ?

    On lance vraiment le jeu temoin et on lit son compteur pendant qu il
    tourne. La version precedente passait --essai a nuit-credits.py, qui est
    le mode « montre sans rien lancer » : RetroArch ne demarrait jamais, la
    lecture ne pouvait qu echouer, et le controle accusait le coeur.

    Renvoie le nom que le coeur annonce, ou None si on ne doit pas balayer.
    """
    systeme, jeu, adresse = TEMOIN
    nuit = outil_nuit()
    base = nuit.base_charger(BASE)          # convertit la base si besoin
    fiche = (base.get("jeux") or {}).get(
        nuit.cle(nuit.COEURS_NOMMES.get(systeme), jeu))
    if not fiche:
        journal("temoin %s absent de la base : controle impossible" % jeu)
        return None

    chemin = rom_du_jeu(systeme, jeu)
    if not chemin:
        journal("temoin %s : rom introuvable dans %s/%s" % (jeu, ROMS, systeme))
        return None

    journal("controle du temoin %s, adresse attendue 0x%04X" % (jeu, adresse))
    jamais = lambda: None                   # le controle ne s interrompt pas
    borne = nuit.Borne("127.0.0.1", False, True)
    try:
        # RetroArch rate un demarrage sur cinq environ : on relance, sinon le
        # controle condamnerait un coeur parfaitement sain.
        en_cours = nuit.lancer_avec_reprises(borne, systeme, jeu, chemin,
                                             jamais, journal)
        if isinstance(en_cours, str):
            journal("temoin : %s. ARRET." % en_cours)
            return None
        if not en_cours:
            journal("temoin : RetroArch n a pas demarre le jeu en %d "
                    "tentatives. ARRET." % nuit.ESSAIS_LANCEMENT)
            return None
        coeur = en_cours[1]

        taille = nuit.patienter(borne.mesurer, nuit.ATTENTE_RAM, jamais)
        if not taille:
            journal("temoin : le coeur %s n expose pas sa RAM. ARRET." % coeur)
            return None
        borne.taille = taille

        if not nuit.attendre_vivant(borne, jamais):
            journal("temoin : le jeu ne s anime pas, lecture non fiable. ARRET.")
            return None

        octets = borne.lire(adresse, 1)
        if octets is None:
            journal("temoin : 0x%04X illisible sous le coeur %s — il ne range "
                    "pas sa memoire au meme endroit. ARRET." % (adresse, coeur))
            return None
        valeur = octets[0]
        if valeur > 99:
            journal("temoin : 0x%04X vaut %d sous %s, ce n est pas un nombre "
                    "de credits plausible. ARRET." % (adresse, valeur, coeur))
            return None

        attendu = nuit.COEURS_NOMMES.get(systeme)
        if nuit.normaliser_coeur(coeur) != nuit.normaliser_coeur(attendu):
            journal("temoin : le coeur s annonce « %s » et non « %s » — les "
                    "fiches d ici lui seront propres, celles de la borne "
                    "restent intactes" % (coeur, attendu))
        journal("temoin : 0x%04X vaut %d sous « %s » — coherent, on peut y aller"
                % (adresse, valeur, coeur))
        return coeur
    finally:
        borne.quitter()
        borne.arreter_processus()


def options_coeur(systeme, coeur):
    """Le nom observe ne vaut que pour les systemes du meme coeur."""
    if coeur and systeme in FAMILLE_TEMOIN:
        return ["--coeur-nomme", coeur]
    return []


def restant(systeme, coeur):
    """Combien de jeux restent a traiter sur ce systeme."""
    sortie = subprocess.run(
        [sys.executable, os.path.join(OUTILS, "nuit-credits.py"),
         "--direct", "--essai", "--systeme", systeme, "--base", BASE,
         "--roms", ROMS] + options_coeur(systeme, coeur),
        capture_output=True, text=True).stdout
    for ligne in sortie.splitlines():
        if "jeu(x) au total" in ligne:
            try:
                return int(ligne.split()[0])
            except ValueError:
                pass
    return 0


def balayer(systeme, coeur, reessayer=False):
    """Un passage complet sur un systeme. Renvoie le code de sortie."""
    commande = [sys.executable, "-u", os.path.join(OUTILS, "nuit-credits.py"),
                "--direct", "--rapide", "--roms", ROMS,
                "--systeme", systeme, "--base", BASE, "--arret", ARRET]
    commande += options_coeur(systeme, coeur)
    if reessayer:
        commande.append("--reessayer")
    chemin = os.path.join(JOURNAUX, "%s-%s.log" % (systeme, time.strftime("%Y%m%d-%H%M")))
    os.makedirs(JOURNAUX, exist_ok=True)
    with open(chemin, "w") as sortie:
        return subprocess.run(commande, stdout=sortie, stderr=subprocess.STDOUT).returncode


def main():
    journal("=== balayage continu : demarrage ===")
    coeur = verifier_temoin()
    if coeur is None:
        journal("le controle du temoin a echoue : on ne balaye pas.")
        return 1

    while not arret_demande():
        travail = False
        for systeme in SYSTEMES:
            if arret_demande():
                break
            if not os.path.isdir(os.path.join(ROMS, systeme)):
                continue
            n = restant(systeme, coeur)
            if n:
                journal("%s : %d jeu(x) a traiter" % (systeme, n))
                balayer(systeme, coeur)
                travail = True
                continue
            # Systeme fini : on tente une fois les ecartes recuperables.
            journal("%s : termine, reprise des ecartes" % systeme)
            if balayer(systeme, coeur, reessayer=True) == 0:
                travail = True

        if arret_demande():
            break
        if not travail:
            journal("plus rien a faire — nouvelle passe dans %d min"
                    % (REPOS_ENTRE_TOURS / 60))
        temps = 0.0
        while temps < REPOS_ENTRE_TOURS and not arret_demande():
            time.sleep(10.0)
            temps += 10.0

    journal("=== arret demande, tout est sauve ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
