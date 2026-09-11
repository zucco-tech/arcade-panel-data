#!/usr/bin/env python3
"""Faux RetroArch : repond comme le vrai, sur une RAM qu'on pilote."""
import random, socket, struct, threading, time

class FauxRetroArch(threading.Thread):
    daemon = True
    def __init__(self, port, taille=0x10000, adresse_credits=0x1234, jeu="testgame",
                 miroirs=()):
        super().__init__()
        self.port = port
        self.taille = taille
        self.adresse = adresse_credits
        self.miroirs = tuple(miroirs)   # le meme compteur, range ailleurs aussi
        self.jeu = jeu
        self.ram = bytearray(random.randrange(256) for _ in range(taille))
        self.ram[self.adresse] = 0
        for m in self.miroirs:
            self.ram[m] = 0
        self.stop = False
        self.commandes = 0

    def bruit(self, combien=300):
        """Le jeu vit : des centaines d'octets bougent en permanence."""
        for _ in range(combien):
            a = random.randrange(self.taille)
            if a == self.adresse or a in self.miroirs:
                continue
            self.ram[a] = (self.ram[a] + random.choice([1, 1, 1, 2, 255])) & 0xFF

    def credits(self, delta):
        valeur = max(0, self.ram[self.adresse] + delta) & 0xFF
        self.ram[self.adresse] = valeur
        for m in self.miroirs:
            self.ram[m] = valeur
        return valeur

    def animer(self):
        """Un jeu qui tourne fait bouger sa RAM en permanence : c'est a ce
        signe que le releveur sait qu'il peut inserer une piece."""
        while not self.stop:
            if self.jeu:
                self.bruit(60)
            time.sleep(0.3)

    def run(self):
        threading.Thread(target=self.animer, daemon=True).start()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", self.port))
        sock.settimeout(0.2)
        while not self.stop:
            try:
                donnees, source = sock.recvfrom(4096)
            except socket.timeout:
                continue
            self.commandes += 1
            texte = donnees.decode(errors="replace").strip()
            if texte == "GET_STATUS":
                # Pas de jeu en cours : le vrai RetroArch ne repond pas PLAYING.
                r = ("GET_STATUS PLAYING FinalBurn Neo,%s,crc32=0" % self.jeu
                     if self.jeu else "GET_STATUS CONTENTLESS")
            elif texte.startswith("READ_CORE_RAM"):
                if not self.jeu:
                    continue                    # aucun jeu : aucune RAM
                try:
                    _, adr, n = texte.split()
                    adr, n = int(adr, 16), int(n)
                except ValueError:
                    continue
                if adr >= self.taille or n > 16384 or adr + n > self.taille:
                    r = "READ_CORE_RAM %x -1" % adr
                else:
                    r = "READ_CORE_RAM %x %s" % (
                        adr, " ".join("%02X" % o for o in self.ram[adr:adr + n]))
            else:
                continue
            # Une commande par image, comme le vrai.
            time.sleep(1 / 60)
            sock.sendto(r.encode(), source)
        sock.close()
