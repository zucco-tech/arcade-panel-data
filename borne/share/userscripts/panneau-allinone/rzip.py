"""Lit une sauvegarde d etat RetroArch, compressee (RZIP) ou non.

Format RZIP : « #RZIPv1# », taille des morceaux (uint32), taille totale
decompressee (uint64), puis pour chaque morceau sa taille compressee (uint32)
suivie d un flux zlib. Sans cet en-tete, le fichier est l etat brut."""
import struct, zlib

def lire_etat(chemin):
    with open(chemin, "rb") as fh:
        d = fh.read()
    if len(d) < 64:
        raise ValueError("fichier d etat vide ou tronque (%d octets)" % len(d))
    if not (d[:6] == b"#RZIPv" and d[7:8] == b"#"):     # #RZIPv<version>#
        return d
    morceau, total = struct.unpack_from("<IQ", d, 8)
    sortie, pos = [], 20
    while pos + 4 <= len(d):
        taille = struct.unpack_from("<I", d, pos)[0]
        pos += 4
        sortie.append(zlib.decompress(d[pos:pos + taille]))
        pos += taille
    brut = b"".join(sortie)
    if len(brut) != total:
        raise ValueError("RZIP : %d octets lus, %d annonces" % (len(brut), total))
    return brut

if __name__ == "__main__":
    import sys
    b = lire_etat(sys.argv[1])
    print("%d octets decompresses" % len(b))
