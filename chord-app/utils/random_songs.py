import random


POP_SONGS = [
    "Blanco y Negro - Malú",
    "Como hablar - Amaral",
    "Con solo una sonrisa - Melendi",
    "Cruz de navajas - Mecano",
    "El principio de algo - LaLaLoveYou",
    "Inmortal - La Oreja de Van Gogh",
    "Rompeolas - Martin",
    "Si no estás - El sueño de morfeo",
    "Superestrella - Aitana",
    "Zapatillas - El canto del loco"
]


INDIE_SONGS = [
    "El lago de mi pena - Barry B, Gara Durán",
    "Dame Estrellas o Limones - Family",
    "Déjalo ir - Martin",
    "El Destello - Juanjo Bona, Martin",
    "Nada debería fallar - La buena vida",
    "Nadadora - Martin",
    "Nananai - Amaia",
    "Pekin - El buen hijo",
    "Un día más (de septiembre) - Malmo 404",
    "Voy con todo - Ralphie choo"
]


FOLK_SONGS = [
    "Eaea - Blanca Paloma",
    "Mi estrella blanca - Fondo Flamenco",
    "La Magallonera - Juanjo Bona",
    "Mis Tías - Juanjo Bona",
    "Moncayo - Juanjo Bona",
    "Me miras pero no me ves - María José Llergo",
    "Que viva España - Manolo Escobar",
    "A tu vera - Salma, Juanjo Bona",
    "Viva el pasodoble - Rocío Jurado"
]

SONGS = [
    "Blanco y Negro - Malú",
    "Como hablar - Amaral",
    "Con solo una sonrisa - Melendi",
    "Cruz de navajas - Mecano",
    "El principio de algo - LaLaLoveYou",
    "Inmortal - La Oreja de Van Gogh",
    "Rompeolas - Martin",
    "Si no estás - El sueño de morfeo",
    "Superestrella - Aitana",
    "Zapatillas - El canto del loco",
    "El lago de mi pena - Barry B, Gara Durán",
    "Dame Estrellas o Limones - Family",
    "Déjalo ir - Martin",
    "El Destello - Juanjo Bona, Martin",
    "Nada debería fallar - La buena vida",
    "Nadadora - Martin",
    "Nananai - Amaia",
    "Pekin - El buen hijo",
    "Un día más (de septiembre) - Malmo 404",
    "Voy con todo - Ralphie choo",
    "Eaea - Blanca Paloma",
    "Mi estrella blanca - Fondo Flamenco",
    "La Magallonera - Juanjo Bona",
    "Mis Tías - Juanjo Bona",
    "Moncayo - Juanjo Bona",
    "Me miras pero no me ves - María José Llergo",
    "Que viva España - Manolo Escobar",
    "A tu vera - Salma, Juanjo Bona",
    "Viva el pasodoble - Rocío Jurado"
]

def pick_songs(song_list, genre):
    song_list = list(song_list)

    n = 1 if genre == "SONGS" else 3

    chosen = random.sample(song_list, n)

    return [f"{genre} | {song}" for song in chosen]


def get_random_songs_txt(genre):

    selected = []

    if genre == "SONGS":
        selected.extend(
            pick_songs(SONGS, "SONGS")
        )
    else:
        selected.extend(
            pick_songs(POP_SONGS, "Pop")
        )

        selected.extend(
            pick_songs(INDIE_SONGS, "Indie")
        )

        selected.extend(
            pick_songs(
                FOLK_SONGS,
                "Folklore Español"
            )
        )

    return "\n".join(selected)

    