-- Cherche le compteur de credits d un jeu, DANS MAME.
--
-- MAME n expose pas sa memoire de travail au frontend libretro : sur dix
-- jeux tires au hasard, un seul rendait un pointeur, et fige. En revanche
-- MAME embarque un interpreteur Lua, et comme on lui donne sa ligne de
-- commande (fichier .cmd), on peut lui faire executer ce script — qui, lui,
-- voit la memoire ET les entrees declarees par le pilote du jeu.
--
-- La methode est la meme que pour les autres coeurs : une piece doit faire
-- monter un octet de exactement un, et le START doit le faire descendre.
-- Ici on a mieux qu ailleurs : les entrees sont NOMMEES (« Coin 1 »,
-- « 1 Player Start »), donc on appuie au bon endroit sans deviner.
--
-- Appele par MAME ainsi :
--     <jeu> -rompath <dossier> -autoboot_script mame-credits.lua
--            -autoboot_delay 1
-- Le resultat est ecrit dans le fichier nomme par MAME_SORTIE, en JSON.

local SORTIE = os.getenv("MAME_SORTIE") or "/tmp/mame-credits.json"
local ATTENTE_DEMARRAGE = 12      -- secondes de jeu avant la premiere piece
local ATTENTE_PIECE = 2           -- apres chaque piece
local ATTENTE_START = 4           -- apres le START
local PIECES = 4
local ACCORDS_MIN = 2
local OCTETS_MAX = 1024 * 1024    -- on ne photographie pas plus que cela

local mach = manager.machine

-- Les zones de RAM du processeur, telles que le PILOTE les declare.
-- MAME publie la carte de son espace d adressage, avec le type de chaque
-- zone : « rom », « ram », « port », « delegate »... On ne garde que la RAM.
-- Les « shares » ne suffisaient pas : chez Pac-Man ils ne couvrent que la
-- memoire video, et le releve trouvait le chiffre AFFICHE a l ecran au lieu
-- du compteur.
local function zones()
    local liste = {}
    local total = 0
    local espace = mach.devices[":maincpu"].spaces["program"]
    local ok = pcall(function()
        for _, e in ipairs(espace.map.entries) do
            if tostring(e.read.handlertype) == "ram" and total < OCTETS_MAX then
                local debut, fin = e.address_start, e.address_end
                local taille = fin - debut + 1
                if total + taille > OCTETS_MAX then taille = OCTETS_MAX - total end
                liste[#liste + 1] = {debut = debut, taille = taille, espace = espace}
                total = total + taille
            end
        end
    end)
    if not ok then return {}, 0 end
    return liste, total
end


local function photo(liste)
    local vue = {}
    for i, zone in ipairs(liste) do
        local octets = {}
        local espace = zone.espace
        local debut = zone.debut
        for decalage = 0, zone.taille - 1 do
            octets[decalage] = espace:read_u8(debut + decalage)
        end
        vue[i] = octets
    end
    return vue
end

-- Les octets qui valent exactement un de plus, en binaire ou en BCD.
local function montes(avant, apres, liste)
    local trouves = {}
    for i, zone in ipairs(liste) do
        local a, b = avant[i], apres[i]
        for adresse = 0, zone.taille - 1 do
            local vieux, neuf = a[adresse], b[adresse]
            if vieux < 0x99 then
                if neuf == (vieux + 1) % 256
                   or (vieux % 16 == 9 and neuf == vieux + 7) then
                    trouves[#trouves + 1] = {zone = i, adresse = adresse}
                end
            end
        end
    end
    return trouves
end

-- Une entree par son nom, dans n importe quel port.
local function entree(motifs)
    for tag, port in pairs(mach.ioport.ports) do
        for nom, champ in pairs(port.fields) do
            for _, motif in ipairs(motifs) do
                if nom == motif then return champ, tag .. "/" .. nom end
            end
        end
    end
    return nil, nil
end

local function appuyer(champ, secondes)
    if not champ then return end
    champ:set_value(1)
    emu.wait(0.1)
    champ:set_value(0)
    emu.wait(secondes)
end

local function clef(c) return c.zone .. ":" .. c.adresse end

local function ecrire(contenu)
    local fichier = io.open(SORTIE, "w")
    if fichier then
        fichier:write(contenu)
        fichier:close()
    end
end

local function texte(v)
    return '"' .. tostring(v):gsub('"', "'") .. '"'
end

-- --- le releve -------------------------------------------------------------

emu.wait(ATTENTE_DEMARRAGE)

local liste, total = zones()
if total == 0 then
    ecrire('{"jeu": ' .. texte(mach.system.name) .. ', "erreur": "aucune RAM declaree"}')
    return
end

local piece, nom_piece = entree({"Coin 1", "Coin"})
local start, nom_start = entree({"1 Player Start", "P1 Start", "Start 1", "Start"})
if not piece then
    ecrire('{"jeu": ' .. texte(mach.system.name) .. ', "erreur": "pas de monnayeur declare",'
           .. ' "ram": ' .. total .. '}')
    return
end

local accords = {}
local avant = photo(liste)
for n = 1, PIECES do
    appuyer(piece, ATTENTE_PIECE)
    local apres = photo(liste)
    for _, c in ipairs(montes(avant, apres, liste)) do
        local k = clef(c)
        accords[k] = (accords[k] or {zone = c.zone, adresse = c.adresse, fois = 0})
        accords[k].fois = accords[k].fois + 1
    end
    avant = apres
end

-- Le START doit faire DESCENDRE : c est ce qui distingue un solde de
-- credits d un simple total de pieces encaissees.
local meilleur, preuve = nil, nil
for essai = 1, 3 do
    local avant_start = photo(liste)
    appuyer(start, ATTENTE_START)
    local apres_start = photo(liste)
    local candidat = nil
    for _, c in pairs(accords) do
        local vieux = avant_start[c.zone][c.adresse]
        local neuf = apres_start[c.zone][c.adresse]
        if neuf < vieux and (candidat == nil or c.fois > candidat.fois) then
            candidat = c
            preuve = {vieux = vieux, neuf = neuf}
        end
    end
    if candidat and candidat.fois >= ACCORDS_MIN then meilleur = candidat break end
    if candidat and meilleur == nil then meilleur = candidat end
end

if meilleur == nil then
    local combien = 0
    for _ in pairs(accords) do combien = combien + 1 end
    ecrire('{"jeu": ' .. texte(mach.system.name) .. ', "erreur": "candidats non confirmes",'
           .. ' "candidats": ' .. combien .. ', "ram": ' .. total
           .. ', "piece": ' .. texte(nom_piece) .. '}')
    return
end

local zone = liste[meilleur.zone]
local adresse = zone.debut + meilleur.adresse
ecrire('{"jeu": ' .. texte(mach.system.name)
       .. ', "zone": ' .. texte(string.format("0x%04X-0x%04X", zone.debut, zone.debut + zone.taille - 1))
       .. ', "adresse": ' .. adresse
       .. ', "adresse_hex": ' .. texte(string.format("0x%04X", adresse))
       .. ', "accords": ' .. meilleur.fois
       .. ', "avant_start": ' .. (preuve and preuve.vieux or 0)
       .. ', "apres_start": ' .. (preuve and preuve.neuf or 0)
       .. ', "ram": ' .. total
       .. ', "piece": ' .. texte(nom_piece)
       .. ', "start": ' .. texte(nom_start or "?")
       .. '}')
