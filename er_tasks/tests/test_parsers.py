from django.test import SimpleTestCase

from er_tasks.parsers import extract_status, infer_created_via, parse_eva_datetime


class ExtractStatusTests(SimpleTestCase):
    def test_created(self):
        self.assertEqual(extract_status("Создано"), ("", "created"))

    def test_closed(self):
        self.assertEqual(extract_status("Задача закрыта"), ("", "closed"))

    def test_status_change(self):
        text = "Статус изменен на В работе, ожидаем Пчелин Василий Андреевич. Завершите работу"
        self.assertEqual(extract_status(text)[1], "status_change")
        self.assertEqual(extract_status(text)[0], "В работе")

    def test_pause(self):
        text = "Статус изменен на Пауза, ожидаем Пчелин Василий Андреевич. Продолжите работу"
        self.assertEqual(extract_status(text)[1], "paused")

    def test_waiting_for(self):
        text = "Ждем ответа: <del>Слободенюк Валерий Валериевич</del> ➔ <ins>Пчелин Василий Андреевич</ins>"
        value, op = extract_status(text)
        self.assertEqual(op, "waiting_for")
        self.assertEqual(value, "Пчелин Василий Андреевич")

    def test_resolution(self):
        value, op = extract_status(
            "Резолюция: <del>Не указано</del> ➔ <ins>Готово</ins>", "Закрыто"
        )
        self.assertEqual(op, "resolution")
        self.assertEqual(value, "Закрыто")


class CreatedViaTests(SimpleTestCase):
    def test_email(self):
        self.assertEqual(
            infer_created_via('<table class="mail-header">x', "Someone"), "email"
        )

    def test_portal_by_tp(self):
        self.assertEqual(
            infer_created_via(
                '<p data-id="abc">hello', "Пчелин Василий Андреевич"
            ),
            "portal_by_tp",
        )

    def test_portal(self):
        self.assertEqual(infer_created_via('<p data-id="abc">hello', "Other"), "portal")


class DateParseTests(SimpleTestCase):
    def test_iso(self):
        dt = parse_eva_datetime("2026-07-13T08:39:34.622063+03:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 7)
