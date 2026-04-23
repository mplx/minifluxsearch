# Maintainer: developer@mplx.eu

pkgname=minifluxsearch
pkgver=0.1.0
pkgrel=1
pkgdesc='CLI and GUI tool to search Miniflux RSS entries by keyword'
arch=('any')
license=('LGPL-3.0-only')
depends=(
    'python'
    'python-requests'
    'python-click'
    'python-tkcalendar' # AUR
    'tk'
)
makedepends=(
    'python-build'
    'python-hatchling'
    'python-installer'
)
optdepends=(
    'python-pytest: run the test suite'
)
# No source tarball needed — run makepkg from the project root directory.
source=()
sha256sums=()

build() {
    cd "$startdir"
    /usr/bin/python -m build --wheel --no-isolation --outdir "$srcdir"
}

package() {
    /usr/bin/python -m installer --destdir="$pkgdir" "$srcdir"/*.whl

    # System-wide icon (used by the .desktop entry)
    install -Dm644 "$startdir/minifluxsearch/icon.png" \
        "$pkgdir/usr/share/pixmaps/$pkgname.png"

    # Desktop entry so the GUI appears in application menus
    install -Dm644 /dev/stdin \
        "$pkgdir/usr/share/applications/$pkgname.desktop" << 'EOF'
[Desktop Entry]
Name=minifluxsearch
Comment=Search Miniflux RSS entries by keyword
Exec=minifluxsearch-gui
Icon=minifluxsearch
Type=Application
Categories=Network;
Keywords=rss;miniflux;feed;news;reader;
EOF
}
