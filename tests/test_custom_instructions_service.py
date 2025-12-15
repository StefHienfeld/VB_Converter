import unittest


from hienfeld.services.custom_instructions_service import CustomInstructionsService


class TestCustomInstructionsService(unittest.TestCase):
    def test_parse_tsv_lines(self):
        raw = "meeverzekerde\tVullen in partijenkaart\nembargo\tVerwijderen - mag weg\n"
        svc = CustomInstructionsService()
        count = svc.load_instructions(raw)
        self.assertEqual(count, 2)
        self.assertEqual(svc.instructions[0].search_text, "meeverzekerde")
        self.assertEqual(svc.instructions[0].action, "Vullen in partijenkaart")
        self.assertEqual(svc.instructions[1].search_text, "embargo")

    def test_parse_arrow_blocks(self):
        raw = "meeverzekerde ondernemingen\n→ Vullen in partijenkaart\n\nsanctieclausule\n-> Verwijderen\n"
        svc = CustomInstructionsService()
        count = svc.load_instructions(raw)
        self.assertEqual(count, 2)
        self.assertEqual(svc.instructions[0].action, "Vullen in partijenkaart")
        self.assertEqual(svc.instructions[1].action, "Verwijderen")

    def test_contains_match_is_perfect(self):
        raw = "meeverzekerde\tVullen in partijenkaart\n"
        svc = CustomInstructionsService()
        svc.load_instructions(raw)

        match = svc.find_match("Deze clausule gaat over de MeeVerzekerde ondernemer.")
        self.assertIsNotNone(match)
        self.assertEqual(match.instruction.action, "Vullen in partijenkaart")
        self.assertEqual(match.score, 1.0)

    def test_semicolon_fallback_parse(self):
        raw = "meeverzekerde;Vullen in partijenkaart\n"
        svc = CustomInstructionsService()
        count = svc.load_instructions(raw)
        self.assertEqual(count, 1)
        self.assertEqual(svc.instructions[0].search_text, "meeverzekerde")
        self.assertEqual(svc.instructions[0].action, "Vullen in partijenkaart")


if __name__ == "__main__":
    unittest.main()


