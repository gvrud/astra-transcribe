import tempfile
import unittest
from pathlib import Path

from multitool_transcriber.engine import Segment, Transcript, Word
from multitool_transcriber.summary import render_summary, summarize, write_summary


def make_transcript(texts):
    segments = []
    for index, text in enumerate(texts):
        words = []
        for offset, word in enumerate(text.split()):
            start = index * 10 + offset * 0.25
            words.append(Word(word, start, start + 0.2))
        segments.append(Segment(words[0].start, words[-1].end, words))
    return Transcript(Path("meeting.wav"), "test-model", "ru", len(texts) * 10, segments)


TEXTS = [
    "сегодня мы обсуждаем запуск нового проекта и сроки подготовки",
    "команда разработки закончила первый этап и передала макеты дизайнерам",
    "бюджет проекта составляет два миллиона рублей на первый квартал",
    "маркетинг подготовил план продвижения и список каналов коммуникации",
    "руководитель подчеркнул важность обратной связи от пользователей",
    "следующая встреча назначена на пятницу в три часа дня",
    "юридический отдел проверит договор с подрядчиком до конца недели",
    "аналитики соберут метрики первого запуска и подготовят отчёт",
    "дизайнеры обновят мобильную версию интерфейса и проверят доступность",
    "после запуска команда проведёт ретроспективу и скорректирует план",
]


class SummaryTests(unittest.TestCase):
    def test_empty_transcript(self):
        transcript = Transcript(Path("empty.wav"), "model", "ru", 0.0, [])
        self.assertEqual(render_summary(transcript), "Речь не распознана.\n")

    def test_short_transcript(self):
        transcript = make_transcript(TEXTS[:2])
        self.assertEqual(summarize(transcript), "\n\n".join(TEXTS[:2]))

    def test_summary_is_extractive_and_ordered(self):
        transcript = make_transcript(TEXTS)
        summary = summarize(transcript)
        parts = summary.split("\n\n")
        self.assertEqual(len(parts), 2)
        for part in parts:
            self.assertIn(part, TEXTS)
        indexes = [TEXTS.index(part) for part in parts]
        self.assertEqual(indexes, sorted(indexes))

    def test_summary_is_capitalized(self):
        transcript = make_transcript(TEXTS)
        summary = render_summary(transcript)
        for part in summary.strip().split("\n\n"):
            self.assertTrue(part[0].isupper())

    def test_summary_uses_custom_base_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = write_summary(
                make_transcript(TEXTS[:2]),
                temporary,
                base_name="lecture (2)",
            )
            self.assertEqual(Path(path).name, "lecture (2).summary.txt")
            self.assertTrue(Path(path).exists())


if __name__ == "__main__":
    unittest.main()
