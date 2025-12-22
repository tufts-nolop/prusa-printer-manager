from django.db import models
from django.urls import reverse


class Printers(models.Model):
    """
    Represents the physical printers available in Nolop.
    """
    PRINTERS = [
        ("core_one", "Prusa Core One"),
        ("mk4", "Original Prusa MK4")
    ]

    name = models.CharField(max_length=128, unique=True)
    model = models.CharField(max_length=128, choices=PRINTERS)
    host = models.GenericIPAddressField()
    api_key = models.CharField(max_length=128) # might not need it
    date_added = models.DateField(auto_now=False, auto_now_add=False)
    slug = models.SlugField(max_length=64, unique=True)

    staff_notes = models.TextField()
    last_maintenance = models.DateField(auto_now=False, auto_now_add=False, null=True, blank=True)

    # bookkeeping for print count
    last_job_id = models.CharField(max_length=64, null=True, blank=True)

    # stats for curiosity's sake
    total_print_count = models.PositiveIntegerField(null=True, blank=True)
    successful_prints = models.PositiveIntegerField(null=True, blank=True)
    printing_uptime = models.PositiveIntegerField(null=True, blank=True) # minutes
    filament_usage_mm = models.FloatField(null=True, blank=True)
    filament_usage_cm3 = models.FloatField(null=True, blank=True)
    filament_usage_g = models.FloatField(null=True, blank=True)


    class Meta:
        verbose_name_plural = "Printers"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("printers:get_printer", args={self.slug})


class PendingJobUsage(models.Model):
    """
    Tracks filament usage for uploaded files that *might* be printed.
    We match this later when that file actually finishes printing.
    """
    printer = models.ForeignKey(
        Printers,
        on_delete=models.CASCADE,
        related_name="pending_jobs",
    )
    
    # should match job["file"]["refs"]["download"] from the printer
    # e.g. "/PRINT_QUEUE/foo.bgcode"
    remote_path = models.CharField(max_length=255)

    filament_mm = models.FloatField(null=True, blank=True)
    filament_g = models.FloatField(null=True, blank=True)
    filament_cm3 = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.printer.slug} :: {self.remote_path}"