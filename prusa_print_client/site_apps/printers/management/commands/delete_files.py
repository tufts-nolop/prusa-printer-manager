import PrusaLinkPy

from django.core.management.base import BaseCommand

from printers.models import Printers


class Command(BaseCommand):
    help = "Automatically clears the folder of 3D print files"

    def handle(self, *args, **options):

        for printer in Printers.objects.all():
            
            try:
                client = PrusaLinkPy.PrusaLinkPy(printer.host, api_key=printer.api_key)

                files = client.get_recursive_files("/PRINT_QUEUE") # we store all uploaded prints in this dir


                for folder_name, mapping in files.items():
                    for display_name, internal_path in mapping.items():
                        # TODO: prob do something about the response, like check it
                        resp = client.delete(internal_path)
            except:
                # if it fails, it fails
                pass