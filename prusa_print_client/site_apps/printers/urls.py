from django.urls import path
from . import views

app_name = 'printers'

urlpatterns = [
    path('', views.PrintersListView.as_view(), name="printers"),
    path('<slug:slug>', views.get_printer, name="get_printer"),

    # api calls
    path("api/printers/status/", views.printers_status_api, name="printers_status_api"),
    path("api/printers/individual-printer/", views.individual_printer_api, name="individual_printer_api"),
    path('api/upload-bgcode/', views.upload_bgcode_api, name='upload_bgcode_api'),
]