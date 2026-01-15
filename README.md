# Nolop Prusa Printer Client

A Django based web app whose primary mission is to send print jobs to Nolop's Prusa 3D printers. It additionally collects data from each printer for Nolop staff to better monitor the current status and health of each printer.


## Setup

It is recommended to either install [Anaconda](https://www.anaconda.com/download) or [Miniconda](https://www.anaconda.com/docs/getting-started/miniconda/install) then run the following to install the environment:

```bash
  conda env create -f environment.yml
```

This command will create a Python environment with all the packages needed to run the server.
(INCOMPLETE SETUP INSTRUSTIONS)

## Roadmap

- Add error handling to:
  - stopping, pausing, and resuming the print job
  - checking printer status
  - bad bgcode file uploads
  - the staff actions (buttons only staff members can access)
- Add staff dashboard to display all the printer analytics
- PrintGuard integration to automatically stop bad/failed prints
- Reporting issues with the printer
- Whatever else anyone wants to see in this thing
