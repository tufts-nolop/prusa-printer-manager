from django.contrib import admin

from . models import Printers, PendingJobUsage


@admin.register(Printers)
class PrintersAdmin(admin.ModelAdmin):
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PendingJobUsage)
class PendingJobUsageAdmin(admin.ModelAdmin):
    search_fields = ['name']