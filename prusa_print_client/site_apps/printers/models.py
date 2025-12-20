from django.db import models
from django.urls import reverse


class Printers(models.Model):
    PRINTERS = [
        ("core_one", "Prusa Core One"),
        ("mk4", "Original Prusa MK4")
    ]

    name = models.CharField(max_length=255, unique=True)
    model = models.CharField(max_length=255, choices=PRINTERS)
    host = models.GenericIPAddressField()
    api_key = models.CharField(max_length=128) # might not need it
    date_added = models.DateField(auto_now=False, auto_now_add=False)
    slug = models.SlugField(max_length=255, unique=True)

    staff_notes = models.TextField()
    last_maintenance = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True)

    # stats for curiosity's sake
    total_print_count = models.PositiveIntegerField(null=True, blank=True)
    successful_prints = models.PositiveIntegerField(null=True, blank=True)
    printing_uptime = models.PositiveIntegerField(null=True, blank=True) # minutes

    class Meta:
        verbose_name_plural = "Printers"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("printers:get_printer", args={self.slug})
