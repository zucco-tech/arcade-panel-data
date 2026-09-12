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
local ATTENTE_DEMARRAGE = 60      -- au plus : on paie des que la machine VIT
local PAS_VIVANT = 2              -- secondes entre deux regards sur la RAM
local OCTETS_VIVANT = 20          -- au-dela, la machine travaille vraiment
local INSISTANCE = 6              -- pieces supplementaires si rien n est confirme
local ATTENTE_PIECE = 2           -- apres chaque piece
local ATTENTE_START = 4           -- apres le START
local PIECES = 4
local ACCORDS_MIN = 2
local OCTETS_MAX = 512 * 1024      -- la RAM de travail fait quelques Ko ; au-dela
                                  -- ce sont des tuiles, et chaque photo coute

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
    if not ok then liste, total = {}, 0 end
    -- ET les shares, toujours. Sur le System 16 d Altered Beast, tout
    -- l espace passe par un delegue (le mapper memoire) : lire les zones
    -- « ram » a travers l espace renvoie autre chose que la RAM reelle, et
    -- CREDITS 9 s affichait a l ecran sans qu un seul octet monte de 1. Les
    -- shares sont la memoire brute, hors mapper. Un octet vu deux fois ne
    -- gene pas : le START tranche.
    -- Les petits shares d abord : la RAM de travail fait quelques Ko, les
    -- memoires de tuiles et les ROM partagees font des centaines de Ko. Sur
    -- Alien Syndrome, pris dans l ordre du hasard, le plafond etait atteint
    -- avant que la RAM de travail n y soit — et aucune piece ne comptait.
    local parts = {}
    for tag, part in pairs(mach.memory.shares) do
        if part.size > 0 then parts[#parts + 1] = {tag = tag, part = part} end
    end
    table.sort(parts, function(a, b) return a.part.size < b.part.size end)
    for _, p in ipairs(parts) do
        local taille = p.part.size
        if total < OCTETS_MAX then
            if total + taille > OCTETS_MAX then taille = OCTETS_MAX - total end
            liste[#liste + 1] = {debut = 0, taille = taille, part = p.part, tag = p.tag}
            total = total + taille
        end
    end
    return liste, total
end


local function photo(liste)
    local vue = {}
    for i, zone in ipairs(liste) do
        local octets = {}
        if zone.part then
            local part = zone.part
            for decalage = 0, zone.taille - 1 do
                octets[decalage] = part:read_u8(decalage)
            end
        else
            local espace = zone.espace
            local debut = zone.debut
            for decalage = 0, zone.taille - 1 do
                octets[decalage] = espace:read_u8(debut + decalage)
            end
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

local liste, total = zones()
if total == 0 then
    ecrire('{"jeu": ' .. texte(mach.system.name) .. ', "erreur": "aucune RAM declaree"}')
    return
end

local piece, nom_piece = entree({"Coin 1", "Coin"})
local piece2 = entree({"Coin 2"})
local start, nom_start = entree({"1 Player Start", "P1 Start", "Start 1", "Start"})
-- Pas de START declare ? Des cartes demarrent avec un bouton de jeu (The
-- Three Stooges n a que Coin 1, Coin 2 et ses boutons). On prend alors le
-- premier bouton du joueur 1 : c est ce qu un joueur ferait.
if not start then
    start, nom_start = entree({"P1 Button 1", "Button 1", "P1 Fire", "Fire 1", "Fire", "P1 Button 2", "Button 2"})
end

-- On attend que la machine VIVE — que sa RAM bouge — au lieu d un delai
-- fixe : Altered Beast met plus de douze secondes a demarrer, et une piece
-- glissee dans une carte en plein test de memoire n existe pas.
local function attendre_vivant()
    local avant = photo(liste)
    local attendu = 0
    while attendu < ATTENTE_DEMARRAGE do
        emu.wait(PAS_VIVANT)
        attendu = attendu + PAS_VIVANT
        local apres = photo(liste)
        local bouge = 0
        for i, zone in ipairs(liste) do
            local a, b = avant[i], apres[i]
            for adresse = 0, zone.taille - 1 do
                if a[adresse] ~= b[adresse] then bouge = bouge + 1 end
            end
        end
        avant = apres
        if bouge > OCTETS_VIVANT and attendu >= 2 * PAS_VIVANT then
            emu.wait(4)
            return attendu
        end
    end
    return nil
end
local vivant = attendre_vivant()
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

-- Rien de confirme : on insiste, en alternant les deux monnayeurs (des
-- cartes n acceptent qu une piece par fente avant un temps mort), et en
-- reessayant le START apres chaque paire de pieces.
if meilleur == nil and (piece or piece2) then
    for n = 1, INSISTANCE do
        local avant_i = photo(liste)
        if n % 2 == 0 and piece2 then appuyer(piece2, ATTENTE_PIECE) else appuyer(piece, ATTENTE_PIECE) end
        local apres_i = photo(liste)
        for _, c in ipairs(montes(avant_i, apres_i, liste)) do
            local k = clef(c)
            accords[k] = (accords[k] or {zone = c.zone, adresse = c.adresse, fois = 0})
            accords[k].fois = accords[k].fois + 1
        end
        if n % 2 == 0 then
            local avant_start = photo(liste)
            appuyer(start, ATTENTE_START)
            local apres_start = photo(liste)
            for _, c in pairs(accords) do
                local vieux = avant_start[c.zone][c.adresse]
                local neuf = apres_start[c.zone][c.adresse]
                if neuf < vieux and c.fois >= ACCORDS_MIN
                   and (meilleur == nil or c.fois > meilleur.fois) then
                    meilleur = c
                    preuve = {vieux = vieux, neuf = neuf}
                end
            end
            if meilleur then break end
        end
    end
end

if meilleur == nil then
    local combien = 0
    for _ in pairs(accords) do combien = combien + 1 end
    ecrire('{"jeu": ' .. texte(mach.system.name) .. ', "erreur": '
           .. (vivant and '"candidats non confirmes"' or '"jeu inanime"')
           .. ', "candidats": ' .. combien .. ', "ram": ' .. total
           .. ', "piece": ' .. texte(nom_piece) .. '}')
    return
end

local zone = liste[meilleur.zone]
local adresse = zone.debut + meilleur.adresse
local nom_zone = zone.tag or string.format("0x%04X-0x%04X", zone.debut, zone.debut + zone.taille - 1)
ecrire('{"jeu": ' .. texte(mach.system.name)
       .. ', "zone": ' .. texte(nom_zone)
       .. ', "adresse": ' .. adresse
       .. ', "adresse_hex": ' .. texte(string.format("0x%04X", adresse))
       .. ', "accords": ' .. meilleur.fois
       .. ', "avant_start": ' .. (preuve and preuve.vieux or 0)
       .. ', "apres_start": ' .. (preuve and preuve.neuf or 0)
       .. ', "ram": ' .. total
       .. ', "piece": ' .. texte(nom_piece)
       .. ', "start": ' .. texte(nom_start or "?")
       .. '}')
