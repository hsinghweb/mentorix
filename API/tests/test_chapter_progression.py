from app.data.syllabus_structure import SYLLABUS_CHAPTERS, chapter_display_name


def test_all_14_chapters_present_and_ordered():
    numbers = [int(c["number"]) for c in SYLLABUS_CHAPTERS]
    assert numbers == list(range(1, 15))


def test_chapter_display_name_contract():
    assert chapter_display_name(1) == "Chapter 1"
    assert chapter_display_name(14) == "Chapter 14"

