from django.contrib import admin

from . models import Printers


@admin.register(Printers)
class PrintersAdmin(admin.ModelAdmin):
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}