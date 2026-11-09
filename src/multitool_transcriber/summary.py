from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from .engine import Transcript
from .outputs import capitalize_sentences, unique_path

STOPWORDS = frozenset(
    """
    и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по
    только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли
    если уже или ни быть был него до вас нибудь опять уж вам ведь там потом себя
    ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без
    будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой
    совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех
    никогда можно при наконец два об другой хоть после над больше тот через эти нас
    про всего них какая много разве три эту моя впрочем хорошо свою этой перед
    иногда лучше чуть том нельзя такой им более всегда конечно всю между это очень
    также кроме вроде просто который которая которые которого которой которых свой
    свои своих ваш ваши наш наши этим этих ими ею нею
    """.split()
)

WORD_PATTERN = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return [
        word
        for word in WORD_PATTERN.findall(text.lower())
        if len(word) > 2 and word not in STOPWORDS
    ]


def summarize(transcript: Transcript, ratio: float = 0.2, max_segments: int = 8) -> str:
    segments = [segment for segment in transcript.segments if segment.text.strip()]
    count = len(segments)
    if count == 0:
        return ""
    if count <= 2:
        return "\n\n".join(segment.text.strip() for segment in segments)

    documents = [_tokens(segment.text) for segment in segments]
    document_frequency: Counter[str] = Counter()
    for document in documents:
        document_frequency.update(set(document))
    idf = {
        term: math.log((count + 1) / (frequency + 1)) + 1.0
        for term, frequency in document_frequency.items()
    }

    scored: list[tuple[float, int]] = []
    for index, (segment, document) in enumerate(zip(segments, documents)):
        if not document:
            scored.append((0.0, index))
            continue
        frequencies = Counter(document)
        weight = sum(value * idf.get(term, 1.0) for term, value in frequencies.items())
        score = weight / math.sqrt(len(document))
        if index == 0:
            score *= 1.15
        scored.append((score, index))

    limit = max(1, min(max_segments, round(count * ratio)))
    if count >= 6:
        limit = max(2, limit)
    chosen = sorted(
        sorted(scored, key=lambda item: (-item[0], item[1]))[:limit],
        key=lambda item: item[1],
    )
    return "\n\n".join(segments[index].text.strip() for _, index in chosen)


def render_summary(transcript: Transcript, capitalize: bool = True) -> str:
    text = summarize(transcript)
    if not text:
        return "Речь не распознана.\n"
    if capitalize:
        text = capitalize_sentences(text)
    return text.rstrip() + "\n"


def write_summary(
    transcript: Transcript,
    output_dir: str | Path,
    *,
    capitalize: bool = True,
    overwrite: bool = True,
    base_name: str | None = None,
) -> str:
    destination = Path(output_dir).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    base = base_name if base_name else (transcript.source.stem or "audio")
    path = destination / f"{base}.summary.txt"
    if not overwrite:
        path = unique_path(path)
    path.write_text(render_summary(transcript, capitalize=capitalize), encoding="utf-8")
    return str(path)
