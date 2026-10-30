import json
import math
from enum import IntEnum


class Points(IntEnum):
    # подошла категория - добавляем столько-то баллов
    GENRE = 2
    MOOD = 3
    AUDIENCE = 1
    VOLUME = 1
    ERA = 1


GENRE_MAPPING = {
    'fantasy': ['fantasy', 'paranormal'],
    'detective': ['mystery', 'thriller', 'crime'],
    'romance': ['romance'],
    'history': ['historical', 'historical fiction', 'history'],
    'nonfiction': ['non-fiction', 'nonfiction'],
    'any': [],
}

AUDIENCE_MAPPING = {
    'kids': [
        'children',
        'young-adult',
        'young adult',
        'juvenile fiction',
    ],
    'adults': [
        'adult',
    ],
    'any': [],
}

MOOD_MAPPING = {
    'escape': [
        'fantasy',
        'paranormal',
        'adventure',
        'science fiction',
    ],
    'intrigue': [
        'mystery',
        'thriller',
        'crime',
    ],
    'romance': ['romance', ],
    'fun': [
        'humor',
        'comedy',
    ],
    'learn': [
        'non-fiction',
        'nonfiction',
        'science',
        'history',
        'biography',
    ],
    'any': [],
}

ALLOWED_ANSWERS = {
    'genre': set(GENRE_MAPPING),
    'audience': set(AUDIENCE_MAPPING),
    'rating': {'high', 'any'},
    'volume': {'short', 'medium', 'long', 'any'},
    'era': {'classic', '1950_2000', 'after_2000', 'any'},
}


def to_number(value):
    """
    Превращает строку или число в float.

    Пустое, некорректное или бесконечное значение → None.
    Это нужно, потому что в CSV встречаются пропуски.
    """
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip())
    except (ValueError, TypeError):
        return None
    if not math.isfinite(number):
        return None
    return number


def normalize_genres(value):
    """
    Приводит жанры к списку строк в нижнем регистре.
    """
    if value is None:
        return []

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        value = parsed

    if isinstance(value, str):
        value = [value]

    if not isinstance(value, (list, tuple)):
        return []

    result = []
    for item in value:
        if not isinstance(item, str):
            continue

        for genre in item.split(','):
            genre = genre.strip().lower()

            if genre:
                result.append(genre)

    return result


def contain_keywords(genres, keywords):
    """
    Проверяет совпадение хотя бы одного ключевого слова.
    """
    for genre in genres:
        if genre in keywords:
            return True

    return False


def get_book_rating(book):
    rating = to_number(book.get('rating'))
    if rating is None:
        return None
    if not (0 <= rating <= 5):
        return None

    return rating


def get_book_id(book):
    value = book.get('id')
    if value is None or not str(value).strip():
        raise ValueError('У книги отсутствует ID')

    return str(value).strip()


def validate_answers(preferences, mood):
    """Проверяет, что переданы известные варианты ответов."""
    for question, answer in preferences.items():
        if question not in ALLOWED_ANSWERS:
            raise ValueError(f'Неизвестный вопрос: {question}')
        if answer not in ALLOWED_ANSWERS[question]:
            raise ValueError(f'Неизвестный ответ для {question}: {answer}')

    if mood is not None and mood not in MOOD_MAPPING:
        raise ValueError(f"Неизвестное настроение: {mood}")


def calculate_score(book, preferences, mood, threshold=4.0):
    """
    Оценивает ОДНУ книгу.

    Возвращает:
    - число баллов - книга допускается;
    - None - книга не прошла обязательный фильтр рейтинга.

    book - словарь с данными книги.
    preferences - словарь ответов первичной анкеты.
    mood - строка с ответом вторичной анкеты или None.
    """
    genres = normalize_genres(book.get('genres'))
    rating = get_book_rating(book)

    if preferences.get('rating', 'any') == 'high':
        if rating is None or rating < threshold:
            return None

    score = 0

    selected_genre = preferences.get('genre', 'any')
    genre_keywords = GENRE_MAPPING[selected_genre]

    if contain_keywords(genres, genre_keywords):
        score += Points.GENRE

    mood_keywords = MOOD_MAPPING.get(mood, [])

    if contain_keywords(genres, mood_keywords):
        score += Points.MOOD

    audience = preferences.get('audience', 'any')

    if audience == 'kids':
        if contain_keywords(genres, AUDIENCE_MAPPING['kids']):
            score += Points.AUDIENCE


    elif audience == 'adults':
        if contain_keywords(genres, AUDIENCE_MAPPING['adults']):
            score += Points.AUDIENCE

    pages = to_number(book.get('pages'))
    volume = preferences.get('volume', 'any')

    if pages is not None and pages > 0:
        if volume == 'short' and pages < 250:
            score += Points.VOLUME

        elif volume == 'medium' and 250 <= pages <= 400:
            score += Points.VOLUME

        elif volume == 'long' and pages > 400:
            score += Points.VOLUME

    year = to_number(book.get('pub_year'))
    era = preferences.get('era', 'any')

    if year is not None and year > 0:
        if era == 'classic' and year < 1950:
            score += Points.ERA

        elif era == '1950_2000' and 1950 <= year <= 2000:
            score += Points.ERA

        elif era == 'after_2000' and year > 2000:
            score += Points.ERA

    return score


def recommend(
        books,
        preferences=None,
        mood=None,
        seen=None,
        threshold=4.0,
        limit=50,
):
    """
    Возвращает лучшие книги из переданного списка.

    books - книги из БД, уже без лайкнутых.
    preferences - ответы первичной анкеты.
    mood - ответ опроса настроения.
    seen - ID книг, обработанных в текущей сессии.
    threshold - минимальный рейтинг при выборе 'high'.
    limit - максимальное количество результатов.
    """
    preferences = preferences or {}

    validate_answers(preferences, mood)

    if limit <= 0:
        return []

    threshold = to_number(threshold)

    if threshold is None or not 0 <= threshold <= 5:
        raise ValueError('Порог рейтинга должен быть от 0 до 5')

    seen = {str(book_id) for book_id in (seen or [])}

    results = []

    for source_book in books:
        book = dict(source_book)
        book_id = get_book_id(book)

        if book_id in seen:
            continue

        score = calculate_score(
            book=book,
            preferences=preferences,
            mood=mood,
            threshold=threshold,
        )

        if score is None:
            continue

        result = {
            **book,
            'id': book_id,
            'rating': get_book_rating(book),
            'score': score,
        }

        results.append(result)

    results.sort(
        key=lambda book: (
            -book['score'],
            -(book['rating'] or 0),
            book['id'],
        )
    )

    return results[:limit]
