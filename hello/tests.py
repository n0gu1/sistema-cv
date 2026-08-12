from django.test import TestCase
from django.urls import reverse


class IndexViewTests(TestCase):
    def test_displays_hello_world(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hola, mundo!")
