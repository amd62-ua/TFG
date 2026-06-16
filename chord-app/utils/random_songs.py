import random


POP_SONGS = [
    "Blanco y Negro - Malú",
    "Como hablar - Amaral",
    "Cruz de navajas - Mecano",
    "El principio de algo - LaLaLoveYou & Samuraï",
    "Inmortal - La Oreja de Van Gogh",
    "rompeolas - Martin",
    "Si no estás - El sueño de morfeo",
    "SUPERESTRELLA - Aitana",
    "Zapatillas - El canto del loco"
]


INDIE_SONGS = [
    "El lago de mi pena - Barry B, Gara Durán",
    "Dame Estrellas o Limones - Family",
    "Déjalo ir - Martin",
    "El Destello - Juanjo Bona, Martin",
    "Nada debería fallar - La buena vida",
    "Nadadora - Martin",
    "Nanai - Amaia",
    "Pekin - El buen hijo",
    "Un dia más (de septiembre) - Malmö 404",
    "Voy con todo - Ralphie choo"
]


FOLK_SONGS = [
    "Eaea - Blanca Paloma",
    "Fondo Flamenco - Mi estrella blanca",
    "Juanjo Bona - La Magallonera",
    "Juanjo Bona - Mis Tías",
    "Juanjo Bona - Moncayo",
    "Me miras pero no me ves - María José Llergo",
    "Que viva España - Manolo Escobar",
    "A tu vera - Salma, Juanjo Bona",
    "Viva el pasodoble - Rocío Jurado"
]

def get_random_songs(num_songs=9):
    if num_songs == 1:

        genre = random.choice([
            "Pop",
            "Indie",
            "Folklore Español"
        ])

        if genre == "Pop":
            song = random.choice(POP_SONGS)

        elif genre == "Indie":
            song = random.choice(INDIE_SONGS)

        else:
            song = random.choice(FOLK_SONGS)

        return [
            {
                "genre": genre,
                "song": song
            }
        ]

    songs = []

    for song in random.sample(
        POP_SONGS,
        3
    ):
        songs.append({
            "genre": "Pop",
            "song": song
        })

    for song in random.sample(
        INDIE_SONGS,
        3
    ):
        songs.append({
            "genre": "Indie",
            "song": song
        })

    for song in random.sample(
        FOLK_SONGS,
        3
    ):
        songs.append({
            "genre": "Folklore Español",
            "song": song
        })

    random.shuffle(songs)

    return songs

