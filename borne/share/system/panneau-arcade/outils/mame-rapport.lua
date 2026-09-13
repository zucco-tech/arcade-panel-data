-- Rapporte le nombre de credits d un jeu MAME, pendant la partie.
--
-- Sur la borne, le demon des credits lit la memoire des jeux par RetroArch
-- (READ_CORE_RAM). MAME ne sert pas cette commande : sa memoire n est pas
-- exposee au frontend. Il faut donc lire de l interieur, comme pour le
-- releve : ce script tourne DANS MAME, lance par le fichier mame.ini que
-- le coeur lit au demarrage de chaque jeu (option mame_read_config).
--
-- Il cherche la machine en cours dans la liste des fiches (une ligne par
-- jeu : nom, adresse, zone), puis ecrit le nombre de credits toutes les
-- 200 ms dans un fichier que le demon relit. Sans fiche pour ce jeu, il
-- ecrit « inconnu » et se tait : le demon garde alors son comportement
-- par defaut.
--
-- Fichiers :
--   FICHES   liste des adresses, produite par le PC de releve
--   RAPPORT  ce que le demon lit : « <jeu> <credits> » ou « <jeu> inconnu »

local FICHES = "/recalbox/share/system/panneau-arcade/mame-fiches.txt"
local RAPPORT = "/tmp/mame-credits"
local CADENCE = 0.2                  -- secondes entre deux rapports

local mach = manager.machine
local nom = mach.system.name

local function ecrire(texte)
    local f = io.open(RAPPORT, "w")
    if f then f:write(texte .. "\n") f:close() end
end

-- La fiche de cette machine : « nom adresse zone ».
local function fiche()
    local f = io.open(FICHES, "r")
    if not f then return nil end
    for ligne in f:lines() do
        local n, a, z = ligne:match("^(%S+)%s+(%S+)%s+(%S+)")
        if n == nom then
            f:close()
            return {adresse = tonumber(a), zone = z}
        end
    end
    f:close()
    return nil
end

-- Une fonction qui lit l octet, selon que la zone est un share (memoire
-- brute, hors mapper) ou une plage de l espace du processeur.
local function lecteur(f)
    if f.zone:sub(1, 1) == ":" then
        local part = mach.memory.shares[f.zone]
        if not part then return nil end
        return function() return part:read_u8(f.adresse) end
    end
    local cpu = mach.devices[":maincpu"]
    if not cpu then return nil end
    local espace = cpu.spaces["program"]
    if not espace then return nil end
    return function() return espace:read_u8(f.adresse) end
end

local f = fiche()
local lire = f and lecteur(f)
if not lire then
    ecrire(nom .. " inconnu")
    return
end

-- On rapporte jusqu a la fin de la partie. Un rapport par CADENCE, meme si
-- la valeur n a pas change : le demon sait ainsi que le script est vivant.
while true do
    local ok, valeur = pcall(lire)
    if ok and valeur then
        ecrire(nom .. " " .. valeur)
    end
    emu.wait(CADENCE)
end
