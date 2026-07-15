import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SAMPLE_INPUT = {
    "personal_info": {
        "name": "Carlos", "last_name": "Martinez", "nickname": "Charly",
        "national_id": "38472913", "city": "Rosario", "zodiac_sign": "Leo",
    },
    "birth_data": {"day_of_birth": "7", "month_of_birth": "4", "year_of_birth": "1998"},
    "family_and_relationships": {
        "mother_name": "Susana", "father_name": "Jorge",
        "sibling_names": ["Lucia", "Pedro"], "partner_name": "Valentina",
        "pet_names": ["Rocky", "Luna"], "important_dates": ["14/02/2015"],
    },
    "work_and_career": {"current_company": "Globant", "job_role": "Backend Developer"},
    "interests_and_fandom": {
        "favorite_sport": "football", "favorite_team": "Rosario Central",
        "favorite_celebrity": "Messi", "hobby": "guitar",
    },
    "tech_and_gaming": {
        "favorite_videogame": "Elden Ring", "favorite_game_character": "Malenia",
        "favorite_programming_language": "Python", "gaming_username": "charly_gg",
        "github_username": "cmartinez",
    },
    "vehicles_and_numbers": {"phone_number": "3415678234", "lucky_number": "7"},
}


@pytest.fixture(scope="session")
def field_types():
    return json.loads((ROOT / "config" / "field_types.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sample_input():
    return SAMPLE_INPUT
