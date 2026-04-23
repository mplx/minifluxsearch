from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

a = Analysis(
    ["minifluxsearch/__main_gui__.py"],
    datas=[
        ("minifluxsearch/themes", "minifluxsearch/themes"),
        ("minifluxsearch/icon.png", "minifluxsearch"),
    ],
    hiddenimports=["tkcalendar", "babel.numbers"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="minifluxsearch-gui",
    console=False,
    icon="minifluxsearch/icon.png",
)
